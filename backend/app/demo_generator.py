import random
from datetime import datetime, timedelta
import uuid
from .company_dict import COMPANY_DICT

class DemoGenerator:
    def __init__(self):
        self.companies = [
            "TSMC", "NVIDIA", "Intel", "AMD", "Samsung", "Apple", "Qualcomm", 
            "Broadcom", "Micron", "ASML", "Applied Materials", "Lam Research",
            "Google", "Alphabet", "DeepMind"
        ]
        
        self.topics = [
            "Yield Rate", "Supply Chain", "Geopolitics", "R&D Breakthrough", 
            "Capacity Expansion", "M&A Rumors", "Executive Moves", "Earnings Surprise",
            "AI Model Launch", "Cloud Infrastructure"
        ]
        
        self.actions = [
            "announces", "delays", "accelerates", "halts", "expands", "partners with", 
            "unveils", "struggles with", "optimizes", "secures funding for", "deploys"
        ]
        
        self.targets = [
            "2nm process", "3nm node", "HBM3e memory", "CoWoS packaging", 
            "Arizona fab", "German facility", "AI accelerator chips", "EUV lithography",
            "Gemini 2.0", "TPU v6", "Waymo expansion", "Vertex AI platform"
        ]

    def generate_batch(self, count=10):
        events = []
        
        # Guarantee coverage for top companies
        # We pick 6 random companies from our dictionary to ensure broad coverage
        all_companies = list(COMPANY_DICT.keys())
        random.shuffle(all_companies)
        priority_companies = all_companies[:6]
        
        for company in priority_companies:
            events.append(self.generate_event(forced_company=company))
            
        # Fill the rest with random events
        remaining_slots = count - len(events)
        if remaining_slots > 0:
            for _ in range(remaining_slots):
                events.append(self.generate_event())
            
        return events

    def generate_event(self, forced_company=None):
        if forced_company:
            company = forced_company
        else:
            company = random.choice(self.companies)
            
        # Use specific topics if available in COMPANY_DICT
        if company in COMPANY_DICT:
            topic = random.choice(COMPANY_DICT[company]["topics"])
        else:
            topic = random.choice(self.topics)
            
        action = random.choice(self.actions)
        target = random.choice(self.targets)
        
        # Generate a realistic title
        title = f"{company} {action} {target} amid {topic.lower()} concerns"
        
        # Generate a snippet
        snippet = f"Reports indicate that {company} is making significant moves regarding {target}. " \
                  f"Analysts suggest this could impact the broader {topic.lower()} landscape. " \
                  f"Market reaction has been mixed with focus on long-term implications."
        
        return {
            "event_id": str(uuid.uuid4()),
            "title": title,
            "snippet": snippet,
            "source": "MarketWire",
            "timestamp": datetime.now().isoformat(),
            "company": company,
            "event_type": topic,
            "url": "https://example.com/news"
        }

demo_generator = DemoGenerator()
