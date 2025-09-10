import re
from typing import List

INFORMAL_PATTERNS: List[str] = [
    "hi", "hello", "hey", "what's up", "how are you", "good morning", "good evening", "good afternoon",
    "thank you", "thanks", "yo", "greetings", "sup", "hiya", "hey there", "heya", "howdy",
    "what's good", "wassup", "holla", "cheers", "thank u", "thanx", "ty", "gm", "gn", "morning",
    "evening", "afternoon", "hello there", "hi there", "nice to meet you", "pleasure to meet you",
    "how’s it going", "how you doing", "what’s going on", "yo bro", "yo man", "yo dude", "hey buddy",
    "hey mate", "namaste", "vanakkam", "salaam", "hello sir", "hello ma'am", "hey team", "hello everyone",
    "hey folks", "good day", "greetings of the day", "hope you are doing well",
    "i hope this message finds you well", "dear sir", "dear madam", "dear team", "respected sir",
    "respected madam", "with due respect", "to whom it may concern", "i would like to inquire",
    "may i know", "kindly assist", "thank you for your time", "sincerely", "regards", "best regards",
    "warm regards", "respectfully", "please let me know", "appreciate your help", "i am writing to",
    "thank you in advance", "looking forward to your response", "awaiting your reply",
    "hope you had a great day", "thank you for your attention", "i appreciate your time",
    "your assistance is highly valued",
    # Short keywords added
    "hi", "hello", "hey", "yo", "sup", "hiya", "heya", "howdy", "namaste", "vanakkam", "salaam",
    "gm", "gn", "gd", "gd mrng", "gd night", "gd aftn", "mrng", "morn", "noon", "eve", "nite",
    "ty", "thx", "tnx", "thanx", "thank u", "tq", "pls", "plz", "asap", "brb", "ok", "k", "kk",
    "cheers", "regards", "rgds", "best", "br", "thnx", "tnku", "tysm", "tyvm", "tc", "take care",
    "bro", "broski", "dude", "man", "mate", "buddy", "pal", "folks", "fam", "peeps", "team", 
    "sir", "ma'am", "madam", "boss", "chief",
    "what's up", "what’s good", "wassup", "wazzup", "whatsup", "sup bro", "yo bro", "yo man", "yo dude",
    "good morning", "good evening", "good afternoon", "good day",
    "hello there", "hi there", "hey there", "hey buddy", "hey mate", "hey folks", "hey team", "hello everyone",
    "greetings", "greetings of the day", "respectfully", "sincerely", "warm regards", "best regards",
    "looking forward", "awaiting reply", "hope you are well", "hope you are doing well", 
    "hope this message finds you well", "appreciate your help", "thank you in advance", 
    "thank you for your attention", "your assistance is valued",
    "dear sir", "dear madam", "dear team", "respected sir", "respected madam", "with due respect", 
    "to whom it may concern", "i would like to inquire", "may i know", "kindly assist", 
    "i am writing to", "thank you for your time", "i appreciate your time", "please let me know",
]

ALLOWED_TOPICS: List[str] = [
    "aquaculture", "fish farming", "pisciculture", "fisheries", "catla", "shrimp", "feed management",
    "pond cleaning", "irrigation", "soil health", "poultry", "agriculture", "organic", "crop rotation",
    "harvesting", "fertilizer", "climate", "farming", "biofloc", "hydroponics", "tilapia", "disease",
    "water quality", "aquaponics", "hatchery management", "fish breeding", "livestock", "vermicomposting",
    "greenhouse farming", "integrated farming", "pasture management", "drip irrigation", "pest control",
    "sustainable farming", "seed treatment", "crop yield", "farm equipment", "traceability",
    "fish nutrition", "duck farming", "desilting", "fingerlings",
    "shrimp farming", "crab farming", "carp farming", "aquaculture technology", "water management",
    "fish processing", "aquatic plants", "mariculture", "fish feed formulation", "organic fertilizer",
    "weed management", "microbial inoculants", "fish health management", "fertigation", "soil testing",
    "aquaculture economics", "climate-resilient farming", "agroforestry", "green manure", "integrated pest management",
    "livestock nutrition", "beekeeping", "water pH management", "fish grading", "harvest storage", 
    "biosecurity", "fish pond construction", "aquaculture machinery", "nutrition supplements", "sustainable fisheries",
    # Short keywords added
    "aquaculture", "fish", "fish farm", "pisciculture", "fisheries", "catla", "shrimp", "feed",
    "pond", "cleaning", "irrigation", "soil", "poultry", "agri", "organic", "crop", "rotation",
    "harvest", "fertilizer", "climate", "farm", "biofloc", "hydroponics", "tilapia", "disease",
    "water", "aquaponics", "hatchery", "breeding", "livestock", "vermicompost", "greenhouse",
    "integrated", "pasture", "drip", "pest", "sustainable", "seed", "yield", "equipment", "trace",
    "nutrition", "duck", "desilt", "fingerling",
    "crab", "carp", "mariculture", "plant", "feedform", "organicfert", "weed", "microbes", 
    "health", "ferti", "soiltest", "economics", "resilient", "agroforestry", "greenmanure", "ipm",
    "bee", "ph", "grading", "storage", "biosecurity", "construction", "machinery", "supplements", "sustainablefish"
    "sensor", "aqua", "pondwater", "fishfood", "cultivation", "farmer", "aqualife", "tank", 
    "breed", "spawning", "hatch", "harvested", "aquaplant", "soilmix", "watersoil", "compost",
    "organicmanure", "drainage", "cropcare", "aquamedicine", "diseasecontrol", "seedling", 
    "spray", "crophealth", "landprep", "cattles", "goat", "sheep", "piggery", "dairy", "milk",
    "honey", "bee farm", "aquatest", "qualitytest", "monitoring", "pesticide", "herbicide", 
    "fungicide", "storagehouse", "warehouse", "farmtech", "automation"
]

FALLBACK_TEXT = (
    "<!--FALLBACK-->🐟 Oops! Just a heads-up: **SORRY**\n"
    "I'm trained specifically in **aquaculture, agriculture, fish, and poultry** topics.\n"
    "I was developed by **Aquanex Systems**, so that's my specialty!\n"
    "Please ask me something in those areas — I'd love to help! 🙏"
)

def includes_any(text: str, patterns: List[str]) -> bool:
    low = text.lower()
    return any(p in low for p in patterns)

THINK_BLOCK_RE = re.compile(r"<think>([\s\S]*?)</think>", re.IGNORECASE)

def strip_fallback_marker(text: str) -> str:
    return text.replace("<!--FALLBACK-->", "")
