#!/usr/bin/env python3
"""
External Profile Enrichment Module
Caches web search results to minimize API costs.

Strategy:
1. Try cache first (SQLite/JSON)
2. If stale/missing, use Google Custom Search (free tier)
3. Update cache and serve
4. Schedule monthly refreshes via n8n
"""

import json
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
import hashlib
import time

class ProfileCache:
    """SQLite-based cache for external profile data."""
    
    def __init__(self, db_path: str = "profile_cache.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite cache table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    company_name TEXT PRIMARY KEY,
                    linkedin_url TEXT,
                    linkedin_title TEXT,
                    indeed_url TEXT,
                    glassdoor_url TEXT,
                    glassdoor_rating TEXT,
                    website_url TEXT,
                    cached_at TIMESTAMP,
                    refresh_after TIMESTAMP
                )
            """)
            conn.commit()
    
    def get(self, company_name: str) -> Optional[Dict]:
        """Get cached profile if not stale."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM profiles WHERE company_name = ? AND refresh_after > ?",
                (company_name, datetime.now())
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    'company_name': row[0],
                    'linkedin_url': row[1],
                    'linkedin_title': row[2],
                    'indeed_url': row[3],
                    'glassdoor_url': row[4],
                    'glassdoor_rating': row[5],
                    'website_url': row[6],
                    'cached_at': row[7]
                }
            return None
    
    def set(self, company_name: str, data: Dict, ttl_days: int = 30):
        """Cache profile data with TTL."""
        now = datetime.now()
        refresh_after = now + timedelta(days=ttl_days)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO profiles 
                (company_name, linkedin_url, linkedin_title, indeed_url, glassdoor_url, 
                 glassdoor_rating, website_url, cached_at, refresh_after)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company_name,
                data.get('linkedin_url'),
                data.get('linkedin_title'),
                data.get('indeed_url'),
                data.get('glassdoor_url'),
                data.get('glassdoor_rating'),
                data.get('website_url'),
                now,
                refresh_after
            ))
            conn.commit()
    
    def get_stale_entries(self, limit: int = 100):
        """Get entries needing refresh (for n8n batch job)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT company_name FROM profiles WHERE refresh_after < ? LIMIT ?",
                (datetime.now(), limit)
            )
            return [row[0] for row in cursor.fetchall()]


class ProfileEnricher:
    """Enrich sponsor data with external profiles."""
    
    def __init__(self, google_api_key: Optional[str] = None, 
                 google_cx: Optional[str] = None):
        self.cache = ProfileCache()
        self.google_api_key = google_api_key
        self.google_cx = google_cx
    
    def enrich(self, company_name: str) -> Dict:
        """
        Get enriched profile data for a company.
        Returns cached data or algorithmic fallback.
        """
        # 1. Check cache
        cached = self.cache.get(company_name)
        if cached:
            return {**cached, 'source': 'cache'}
        
        # 2. Try Google Custom Search (if configured)
        if self.google_api_key and self.google_cx:
            try:
                data = self._fetch_from_google(company_name)
                if data:
                    self.cache.set(company_name, data)
                    return {**data, 'source': 'google_api'}
            except Exception as e:
                print(f"Google API error for {company_name}: {e}")
        
        # 3. Fallback to algorithmic links
        return {
            'company_name': company_name,
            'linkedin_url': self._generate_linkedin_search(company_name),
            'indeed_url': self._generate_indeed_search(company_name),
            'glassdoor_url': self._generate_glassdoor_search(company_name),
            'website_url': self._generate_google_search(company_name),
            'source': 'algorithmic'
        }
    
    def _fetch_from_google(self, company_name: str) -> Optional[Dict]:
        """
        Use Google Custom Search API to find actual profiles.
        Free tier: 100 queries/day
        Cost: $5 per 1000 queries after that
        """
        import requests
        
        results = {}
        
        # Search for LinkedIn
        linkedin_data = self._google_search(
            f"{company_name} LinkedIn company UK",
            site="linkedin.com/company"
        )
        if linkedin_data:
            results['linkedin_url'] = linkedin_data.get('link')
            results['linkedin_title'] = linkedin_data.get('title', '').replace(' | LinkedIn', '')
        
        # Search for official website
        website_data = self._google_search(
            f"{company_name} official website UK",
            exclude=['linkedin.com', 'indeed.com', 'glassdoor.com', 'wikipedia.org']
        )
        if website_data:
            results['website_url'] = website_data.get('link')
        
        return results if results else None
    
    def _google_search(self, query: str, site: Optional[str] = None, 
                       exclude: Optional[list] = None) -> Optional[Dict]:
        """Execute Google Custom Search."""
        import requests
        
        if site:
            query = f"site:{site} {query}"
        
        if exclude:
            for domain in exclude:
                query += f" -site:{domain}"
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': self.google_api_key,
            'cx': self.google_cx,
            'q': query,
            'num': 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'items' in data and len(data['items']) > 0:
            return data['items'][0]
        return None
    
    def _generate_linkedin_search(self, company: str) -> str:
        from urllib.parse import quote
        return f"https://www.linkedin.com/search/results/companies/?keywords={quote(company)}"
    
    def _generate_indeed_search(self, company: str) -> str:
        from urllib.parse import quote
        return f"https://www.indeed.com/jobs?q=&l=United+Kingdom&rbc={quote(company)}"
    
    def _generate_glassdoor_search(self, company: str) -> str:
        from urllib.parse import quote
        return f"https://www.glassdoor.com/Search/results.htm?keyword={quote(company)}"
    
    def _generate_google_search(self, company: str) -> str:
        from urllib.parse import quote
        return f"https://www.google.com/search?q={quote(company)}"


# Batch refresh script for n8n
def batch_refresh_stale(limit: int = 50):
    """
    Refresh stale entries. Run this via n8n monthly.
    Only processes companies that need updates.
    """
    enricher = ProfileEnricher(
        google_api_key=os.getenv('GOOGLE_API_KEY'),
        google_cx=os.getenv('GOOGLE_CX')
    )
    
    cache = ProfileCache()
    stale = cache.get_stale_entries(limit=limit)
    
    refreshed = 0
    for company in stale:
        try:
            enricher.enrich(company)
            refreshed += 1
            time.sleep(1)  # Rate limiting
        except Exception as e:
            print(f"Failed to refresh {company}: {e}")
    
    return {'refreshed': refreshed, 'total_stale': len(stale)}


if __name__ == '__main__':
    # Test
    enricher = ProfileEnricher()
    result = enricher.enrich("NHS England")
    print(json.dumps(result, indent=2))
