#!/usr/bin/env python3
"""
UK Sponsor Lookup Tool
Check if a company is a registered UK visa sponsor.

Usage:
    python sponsor_lookup.py --company "Company Name"
    python sponsor_lookup.py --url "https://job-board.com/job/123"
    python sponsor_lookup.py --interactive
"""

import csv
import argparse
import re
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


class FastSponsorLookup:
    """Optimized UK Sponsor Lookup with fast indexing."""
    
    def __init__(self, csv_path: str = "uk_sponsors.csv"):
        self.csv_path = csv_path
        self.sponsors: List[Dict] = []
        self.name_to_sponsors: Dict[str, List[Dict]] = {}
        self.word_index: Dict[str, Set[str]] = {}
        self._load_data()
    
    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        text = re.sub(r'[^\w\s]', '', text.lower())
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _load_data(self):
        """Load and index sponsor data from CSV."""
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"Sponsor CSV not found: {self.csv_path}")
        
        print(f"Loading sponsor data...", file=sys.stderr)
        
        with open(self.csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                org_name = row.get('Organisation Name', '').strip().strip('"')
                if not org_name:
                    continue
                    
                sponsor = {
                    'name': org_name,
                    'city': row.get('Town/City', '').strip().strip('"'),
                    'county': row.get('County', '').strip().strip('"'),
                    'rating': row.get('Type & Rating', '').strip().strip('"'),
                    'route': row.get('Route', '').strip().strip('"')
                }
                self.sponsors.append(sponsor)
                
                # Index by normalized full name
                normalized = self._normalize(org_name)
                if normalized not in self.name_to_sponsors:
                    self.name_to_sponsors[normalized] = []
                self.name_to_sponsors[normalized].append(sponsor)
                
                # Index individual words
                words = normalized.split()
                for word in words:
                    if len(word) > 2:  # Only index words longer than 2 chars
                        if word not in self.word_index:
                            self.word_index[word] = set()
                        self.word_index[word].add(normalized)
        
        print(f"Loaded {len(self.sponsors)} sponsor records", file=sys.stderr)
    
    def _simple_similarity(self, a: str, b: str) -> float:
        """Simple but fast similarity calculation."""
        a_words = set(self._normalize(a).split())
        b_words = set(self._normalize(b).split())
        
        if not a_words or not b_words:
            return 0.0
        
        intersection = len(a_words & b_words)
        union = len(a_words | b_words)
        
        return intersection / union if union > 0 else 0.0
    
    def search(self, query: str, threshold: float = 0.5, max_results: int = 10) -> List[Tuple[Dict, float]]:
        """Fast search using word index with improved fuzzy matching."""
        query_norm = self._normalize(query)
        query_words = [w for w in query_norm.split() if len(w) > 2]
        results = []
        seen = set()
        
        # 1. Check for exact match
        if query_norm in self.name_to_sponsors:
            for sponsor in self.name_to_sponsors[query_norm]:
                key = sponsor['name']
                if key not in seen:
                    results.append((sponsor, 1.0))
                    seen.add(key)
        
        # 2. Check for substring matches (e.g., "Barclays" in "Barclays Bank PLC")
        for name, sponsors in self.name_to_sponsors.items():
            if name in seen:
                continue
            # Query is substring of company name
            if query_norm in name:
                score = 0.9  # High confidence for substring match
                for sponsor in sponsors:
                    results.append((sponsor, score))
                seen.add(name)
            # Company name is substring of query (e.g., "Limited" in query)
            elif len(query_norm) > 5 and name in query_norm:
                score = 0.85
                for sponsor in sponsors:
                    results.append((sponsor, score))
                seen.add(name)
        
        # 3. Word-based matching (fast pre-filter)
        candidate_names = set()
        for word in query_words:
            if word in self.word_index:
                candidate_names.update(self.word_index[word])
        
        # 4. Score candidates with improved algorithm
        for name in candidate_names:
            if name in seen:
                continue
            score = self._simple_similarity(query_norm, name)
            
            # Boost score for partial matches
            query_tokens = set(query_norm.split())
            name_tokens = set(name.split())
            
            # If any query word starts a company name word, boost
            for qt in query_tokens:
                for nt in name_tokens:
                    if nt.startswith(qt) or qt.startswith(nt):
                        score = max(score, 0.7)
                    # Handle abbreviations (e.g., "HSBC" matching "HSBC Bank")
                    if len(qt) >= 3 and qt in nt:
                        score = max(score, 0.75)
            
            if score >= threshold:
                for sponsor in self.name_to_sponsors[name]:
                    results.append((sponsor, score))
                seen.add(name)
        
        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]
    
    def is_sponsor(self, company_name: str, threshold: float = 0.8) -> Optional[Dict]:
        """Check if a specific company is a sponsor."""
        results = self.search(company_name, threshold=threshold, max_results=1)
        if results and results[0][1] >= threshold:
            return results[0][0]
        return None
    
    def _fetch_page_title(self, url: str) -> Optional[str]:
        """Try to fetch page title/company from job listing URL."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = Request(url, headers=headers, timeout=10)
            with urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                
                # Try to extract company from meta tags or JSON-LD
                # Indeed pattern: data-company-name or JSON-LD
                indeed_match = re.search(r'data-company-name="([^"]+)"', html)
                if indeed_match:
                    return indeed_match.group(1)
                
                # JSON-LD structured data
                jsonld_match = re.search(r'<script type="application/ld\+json">([^<]+)</script>', html)
                if jsonld_match:
                    try:
                        data = json.loads(jsonld_match.group(1))
                        if isinstance(data, dict):
                            if 'hiringOrganization' in data:
                                org = data['hiringOrganization']
                                if isinstance(org, dict):
                                    return org.get('name')
                            if 'name' in data and 'job' in url.lower():
                                return data.get('name')
                    except json.JSONDecodeError:
                        pass
                
                # Title tag fallback
                title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1)
                    # Remove common suffixes
                    title = re.sub(r' - (Indeed|LinkedIn|Glassdoor|Jobs).*$', '', title, flags=re.IGNORECASE)
                    title = re.sub(r' \|.*$', '', title)
                    if ' at ' in title.lower():
                        parts = title.split(' at ')
                        if len(parts) >= 2:
                            return parts[-1].strip()
                    return title.strip()
        except (URLError, HTTPError, Exception):
            pass
        return None

    # Known company domains for quick lookup
    KNOWN_COMPANY_DOMAINS = {
        'careers.google.com': 'Google',
        'jobs.apple.com': 'Apple',
        'careers.microsoft.com': 'Microsoft',
        'amazon.jobs': 'Amazon',
        'careers.barclays.co.uk': 'Barclays',
        'jobs.hsbc.co.uk': 'HSBC',
        'careers.nhs.uk': 'NHS',
        'jobs.tesco.com': 'Tesco',
        'careers.sainsburys.co.uk': 'Sainsburys',
    }
    
    def extract_company_from_url(self, url: str) -> Optional[str]:
        """Extract company name from job posting URL.
        
        Returns company name if confident, None otherwise.
        We prioritize accuracy over coverage - false matches hurt user trust.
        """
        url_lower = url.lower()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Check known domains first
        for known_domain, company in self.KNOWN_COMPANY_DOMAINS.items():
            if known_domain in domain:
                return company
        
        # Try to extract from URL patterns
        url_patterns = [
            # LinkedIn company pages - most reliable
            (r'linkedin\.com/company/([^/]+)/?(?:jobs|about)?$', 'linkedin'),
            # Indeed company pages  
            (r'indeed\.(?:com|co\.uk)/cmp/([^/]+)', 'indeed'),
            # Glassdoor company pages
            (r'glassdoor\.(?:com|co\.uk)/Overview/Working-at-([^-]+)-', 'glassdoor'),
            # Reed
            (r'reed\.co\.uk/company/([^/]+)', 'reed'),
            # Totaljobs
            (r'totaljobs\.com/company/([^/]+)', 'totaljobs'),
        ]
        
        for pattern, source in url_patterns:
            match = re.search(pattern, url_lower)
            if match:
                extracted = match.group(1).replace('-', ' ').title()
                cleaned = self._clean_company_name(extracted)
                if cleaned:
                    return cleaned
        
        # Subdomain extraction (careers.company.com)
        subdomain_match = re.match(r'^([^.]+)\.(?:careers?|jobs|apply|workday)\.', domain)
        if subdomain_match:
            company = subdomain_match.group(1).title()
            cleaned = self._clean_company_name(company)
            if cleaned:
                return cleaned
        
        # For job view pages without company in URL, don't guess
        # This prevents false matches that hurt user trust
        unreliable_patterns = [
            'indeed.com/viewjob',
            'indeed.co.uk/viewjob', 
            'linkedin.com/jobs/view',
            'glassdoor.com/job',
            'reed.co.uk/jobs/',
        ]
        
        for pattern in unreliable_patterns:
            if pattern in url_lower:
                # These URLs don't contain company name - would need scraping
                return None
        
        return None
    
    def _clean_company_name(self, name: str) -> Optional[str]:
        """Clean and validate extracted company name."""
        if not name:
            return None
            
        # Remove common noise words
        noise_words = ['Jobs', 'Careers', 'Ltd', 'Limited', 'Inc', 'Corp', 'Corporation', 'PLC', 'LLC']
        for word in noise_words:
            name = re.sub(r'\b' + word + r'\b', '', name, flags=re.IGNORECASE)
        
        name = name.strip()
        
        # Validate
        if len(name) < 2:
            return None
        if not any(c.isalpha() for c in name):
            return None
            
        return name
    
    def format_result(self, sponsor: Dict, score: float = 1.0) -> str:
        """Format a sponsor record for display."""
        status = "CONFIRMED" if score >= 0.8 else "POSSIBLE MATCH"
        icon = "✅" if score >= 0.8 else "⚠️"
        
        lines = [
            f"{icon} {status} (Match: {score:.0%})",
            f"   Company: {sponsor['name']}",
            f"   Location: {sponsor['city']}" + (f", {sponsor['county']}" if sponsor['county'] else ""),
            f"   Rating: {sponsor['rating']}",
            f"   Route: {sponsor['route']}",
        ]
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='UK Visa Sponsor Lookup Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --company "Google UK"
  %(prog)s --url "https://www.linkedin.com/jobs/view/123"
  %(prog)s --interactive
        """
    )
    parser.add_argument('--company', '-c', help='Company name to search')
    parser.add_argument('--url', '-u', help='Job posting URL to analyze')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')
    parser.add_argument('--csv', default='uk_sponsors.csv', help='Path to sponsor CSV file')
    parser.add_argument('--threshold', '-t', type=float, default=0.5, help='Match threshold (0-1)')
    
    args = parser.parse_args()
    
    # Initialize lookup
    try:
        lookup = FastSponsorLookup(args.csv)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Download from: https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers", file=sys.stderr)
        return 1
    
    if args.company:
        print(f"\nSearching for: '{args.company}'\n")
        results = lookup.search(args.company, threshold=args.threshold)
        
        if not results:
            print("No matching sponsors found")
            return 0
        
        for sponsor, score in results[:5]:
            print(lookup.format_result(sponsor, score))
            print()
        
        best_match = results[0]
        print("-" * 50)
        if best_match[1] >= 0.8:
            print("✅ CONFIRMED: This is a registered UK visa sponsor")
        elif best_match[1] >= 0.5:
            print("⚠️  POSSIBLE MATCH: Review results above")
        else:
            print("❌ NOT FOUND: Not a registered sponsor")
        print("-" * 50)
    
    elif args.url:
        print(f"\nAnalyzing URL: {args.url}\n")
        company = lookup.extract_company_from_url(args.url)
        
        if not company:
            print("Could not extract company name from URL")
            print("Try using --company with the company name directly")
            return 0
        
        print(f"Detected company: '{company}'\n")
        results = lookup.search(company, threshold=args.threshold)
        
        if not results:
            print("No matching sponsors found")
            return 0
        
        for sponsor, score in results[:5]:
            print(lookup.format_result(sponsor, score))
            print()
        
        best_match = results[0]
        print("-" * 50)
        if best_match[1] >= 0.8:
            print("✅ CONFIRMED: This company is a registered UK visa sponsor")
        elif best_match[1] >= 0.5:
            print("⚠️  POSSIBLE MATCH: Review results above")
        else:
            print("❌ NOT FOUND: Not a registered sponsor")
        print("-" * 50)
    
    elif args.interactive:
        print("\n" + "=" * 50)
        print("   UK SPONSOR LOOKUP - Interactive Mode")
        print("=" * 50)
        print("Enter a company name or 'quit' to exit\n")
        
        while True:
            try:
                query = input("Company name > ").strip()
                if query.lower() in ('quit', 'exit', 'q'):
                    break
                if not query:
                    continue
                
                results = lookup.search(query, threshold=args.threshold)
                
                if not results:
                    print("No matching sponsors found\n")
                    continue
                
                for sponsor, score in results[:3]:
                    print(lookup.format_result(sponsor, score))
                    print()
                
                best_match = results[0]
                if best_match[1] >= 0.8:
                    print("✅ CONFIRMED: Registered UK visa sponsor\n")
                elif best_match[1] >= 0.5:
                    print("⚠️  POSSIBLE MATCH: Review above\n")
                else:
                    print("❌ NOT FOUND: Not a registered sponsor\n")
                    
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
    
    else:
        parser.print_help()
    
    return 0


if __name__ == '__main__':
    exit(main())
