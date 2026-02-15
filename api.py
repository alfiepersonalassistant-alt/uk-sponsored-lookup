#!/usr/bin/env python3
"""
UK Sponsor Lookup - Web API v2
Restful API with deduplication and external links.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sponsor_lookup import FastSponsorLookup
import os
import sys
import re
import json
from urllib.parse import quote
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Rate limiting - 100 requests per hour per IP
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

CSV_PATH = os.environ.get('SPONSOR_CSV', 'uk_sponsors.csv')
STATS_FILE = 'stats.json'
lookup = None

def load_stats():
    """Load search statistics."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'total_searches': 0, 'last_updated': datetime.now().isoformat()}

def save_stats(stats):
    """Save search statistics."""
    stats['last_updated'] = datetime.now().isoformat()
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f)

def increment_search():
    """Increment search counter."""
    stats = load_stats()
    stats['total_searches'] += 1
    save_stats(stats)
    return stats['total_searches']

@app.before_request
def init_lookup():
    global lookup
    if lookup is None:
        lookup = FastSponsorLookup(CSV_PATH)

def generate_external_links(company_name: str, city: str = None, county: str = None) -> dict:
    """Generate UK-specific external profile links for a company using name + location."""
    
    # Build location-aware search queries
    location_parts = []
    if city and city.strip():
        location_parts.append(city.strip())
    if county and county.strip():
        location_parts.append(county.strip())
    
    location_str = ", ".join(location_parts)
    
    # Company name query
    company_query = quote(company_name)
    
    # Company + Location query (for more specific searches)
    if location_str:
        company_location_query = quote(f"{company_name} {location_str} UK")
        location_query = quote(location_str)
    else:
        company_location_query = company_query
        location_query = "United+Kingdom"
    
    # UK-specific search URLs
    return {
        # LinkedIn - UK focused
        'linkedin_search': f"https://www.linkedin.com/search/results/companies/?keywords={company_query}&location=United%20Kingdom",
        'linkedin_jobs': f"https://www.linkedin.com/jobs/search?keywords={company_query}&location=United%20Kingdom",
        
        # Indeed - UK specific
        'indeed_jobs': f"https://uk.indeed.com/jobs?q={company_query}&l={location_query if location_str else 'United+Kingdom'}",
        'indeed_company': f"https://uk.indeed.com/cmp/{company_query}",
        
        # Glassdoor - UK specific
        'glassdoor_overview': f"https://www.glassdoor.co.uk/Overview/Working-at-{company_query}-EI_IE.htm",
        'glassdoor_jobs': f"https://www.glassdoor.co.uk/Search/results.htm?keyword={company_query}",
        
        # Companies House - UK official registry
        'companies_house': f"https://find-and-update.company-information.service.gov.uk/search?q={company_query}",
        
        # Google - UK focused with location
        'google': f"https://www.google.com/search?q={company_location_query}",
        'google_maps': f"https://www.google.com/maps/search/{quote(company_name + ' ' + location_str) if location_str else company_query}",
        
        # UK-specific job boards
        'reed': f"https://www.reed.co.uk/jobs/{company_query}-jobs",
        'totaljobs': f"https://www.totaljobs.com/jobs/{company_query}",
        'cwjobs': f"https://www.cwjobs.co.uk/jobs/{company_query}",
        
        # Information
        'source': 'uk_specific',
        'location_used': location_str or 'United Kingdom'
    }

def deduplicate_results(results):
    """Deduplicate results by company name, keeping the best match."""
    seen = {}
    
    for sponsor, score in results:
        name = sponsor['name']
        if name not in seen or seen[name]['score'] < score:
            seen[name] = {
                'sponsor': sponsor,
                'score': score
            }
    
    # Convert back to list format, sorted by score
    return [(v['sponsor'], v['score']) for v in sorted(seen.values(), key=lambda x: x['score'], reverse=True)]

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'sponsors_loaded': len(lookup.sponsors) if lookup else 0
    })

@app.route('/api/search', methods=['GET'])
@limiter.limit("30 per minute")  # Stricter limit for searches
def search():
    company = request.args.get('company', '').strip()
    threshold = float(request.args.get('threshold', 0.5))
    limit = int(request.args.get('limit', 10))
    
    if not company:
        return jsonify({'error': 'Company name required'}), 400
    
    # Increment search counter
    total_searches = increment_search()
    
    results = lookup.search(company, threshold=threshold, max_results=50)
    
    # Deduplicate by company name
    results = deduplicate_results(results)
    
    # Limit results
    results = results[:limit]
    
    return jsonify({
        'query': company,
        'count': len(results),
        'results': [
            {
                'name': s['name'],
                'city': s['city'],
                'county': s['county'],
                'rating': s['rating'],
                'route': s['route'],
                'match_score': round(score, 3),
                'is_confirmed': score >= 0.8,
                'links': generate_external_links(s['name'], s.get('city'), s.get('county'))
            }
            for s, score in results
        ]
    })

@app.route('/api/check', methods=['GET'])
def check():
    company = request.args.get('company', '').strip()
    threshold = float(request.args.get('threshold', 0.8))
    
    if not company:
        return jsonify({'error': 'Company name required'}), 400
    
    sponsor = lookup.is_sponsor(company, threshold=threshold)
    
    if sponsor:
        return jsonify({
            'is_sponsor': True,
            'company': sponsor['name'],
            'city': sponsor['city'],
            'county': sponsor['county'],
            'rating': sponsor['rating'],
            'route': sponsor['route'],
            'links': generate_external_links(sponsor['name'], sponsor.get('city'), sponsor.get('county'))
        })
    else:
        return jsonify({
            'is_sponsor': False,
            'message': 'Company not found in sponsor registry'
        })

@app.route('/api/url', methods=['POST'])
@limiter.limit("20 per minute")  # Stricter limit for URL processing
def check_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL required in JSON body'}), 400
    
    url = data['url']
    company = lookup.extract_company_from_url(url)
    
    if not company:
        return jsonify({
            'extracted_company': None,
            'is_sponsor': False,
            'message': 'Could not extract company from URL'
        })
    
    sponsor = lookup.is_sponsor(company)
    
    return jsonify({
        'url': url,
        'extracted_company': company,
        'is_sponsor': sponsor is not None,
        'sponsor_details': {
            **sponsor,
            'links': generate_external_links(sponsor['name'], sponsor.get('city'), sponsor.get('county'))
        } if sponsor else None
    })

@app.route('/api/stats', methods=['GET'])
def stats():
    routes = {}
    ratings = {}
    
    for s in lookup.sponsors:
        route = s['route']
        routes[route] = routes.get(route, 0) + 1
        rating = s['rating']
        ratings[rating] = ratings.get(rating, 0) + 1
    
    search_stats = load_stats()
    
    return jsonify({
        'total_sponsors': len(lookup.sponsors),
        'unique_companies': len(set(s['name'] for s in lookup.sponsors)),
        'top_routes': dict(sorted(routes.items(), key=lambda x: -x[1])[:10]),
        'ratings': ratings,
        'total_searches': search_stats.get('total_searches', 0),
        'stats_last_updated': search_stats.get('last_updated')
    })

@app.route('/', methods=['GET'])
def index():
    """Serve the main HTML interface."""
    return send_from_directory('.', 'index.html')

@app.route('/api', methods=['GET'])
def api_info():
    """API information endpoint."""
    return jsonify({
        'name': 'UK Sponsor Lookup API',
        'version': '2.0',
        'endpoints': {
            '/api/health': 'Health check',
            '/api/search?company=NAME': 'Search sponsors by name',
            '/api/check?company=NAME': 'Quick check if sponsor',
            '/api/url': 'POST - Extract company from URL and check',
            '/api/stats': 'Database statistics'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
