from .llm_tool_base import LLMTool, LLMToolParameter


from datetime import datetime

def number_to_words(n):
    """Convert numbers to spoken words for numbers 1-99"""
    ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
    teens = ['ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 
             'sixteen', 'seventeen', 'eighteen', 'nineteen']
    tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
    
    if n == 0:
        return 'twelve'  # Special case for 12:00
    elif n < 10:
        return ones[n]
    elif n < 20:
        return teens[n - 10]
    else:
        return tens[n // 10] + (' ' + ones[n % 10] if n % 10 != 0 else '')

def ordinal_day(day):
    """Convert day number to ordinal form (1st, 2nd, 3rd, etc.) in words"""
    if 11 <= day <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(day % 10, 4)]
    
    # Convert to spoken ordinal
    if day == 1:
        return "first"
    elif day == 2:
        return "second"
    elif day == 3:
        return "third"
    elif day == 21:
        return "twenty first"
    elif day == 22:
        return "twenty second"
    elif day == 23:
        return "twenty third"
    elif day == 31:
        return "thirty first"
    else:
        return number_to_words(day) + ('th' if suffix == 'th' else '')

def format_time_spoken(dt):
    """Format time in spoken form"""
    hour = dt.hour
    minute = dt.minute
    period = "AM" if hour < 12 else "PM"
    
    # Convert to 12-hour format
    if hour == 0:
        hour = 12
    elif hour > 12:
        hour -= 12
    
    # Special cases for time
    if minute == 0:
        if hour == 12 and dt.hour == 0:
            return "midnight"
        elif hour == 12 and dt.hour == 12:
            return "noon"
        else:
            return f"{number_to_words(hour)} o'clock {period}"
    elif minute == 15:
        return f"quarter past {number_to_words(hour)} {period}"
    elif minute == 30:
        return f"half past {number_to_words(hour)} {period}"
    elif minute == 45:
        next_hour = hour + 1 if hour < 12 else 1
        return f"quarter to {number_to_words(next_hour)} {period}"
    else:
        # Handle minutes with proper formatting
        if minute < 10:
            minute_str = f"oh {number_to_words(minute)}"
        else:
            minute_str = number_to_words(minute)
        return f"{number_to_words(hour)} {minute_str} {period}"

def spoken_datetime(dt=None, include_date=True, include_time=True):
    """
    Convert datetime to spoken format.
    
    Args:
        dt: datetime object (defaults to current time if None)
        include_date: bool, whether to include the date
        include_time: bool, whether to include the time
    
    Returns:
        str: Spoken representation of the date/time
    """
    if dt is None:
        dt = datetime.now()
    
    parts = []
    
    if include_time:
        time_str = format_time_spoken(dt)
        parts.append(time_str)
    
    if include_date:
        weekday = dt.strftime("%A")
        month = dt.strftime("%B")
        day = ordinal_day(dt.day)
        year = dt.year
        
        date_str = f"{weekday}, {month} {day}, {year}"
        
        if include_time:
            # If both date and time, put time first with "on"
            parts = [parts[0] + " on " + date_str]
        else:
            parts.append(date_str)
    
    return " ".join(parts)

class GetDateTime(LLMTool):
    def __init__(self, master_state):
        include_date_param = LLMToolParameter("include_date", "YES if the answer should include the date", required=False)
        include_time_param = LLMToolParameter("include_time", "YES if the answer should include the time", required=False)
        super().__init__("datetime", "This tool provides the time, or the date, or both of them together depending on what the user asks.", [include_date_param, include_time_param], master_state)

    async def invoke(self, args):
        try:
            return spoken_datetime(include_date=args.get("include_date", "no").lower()=="yes", include_time=args.get("include_time", "no").lower()=="yes")                
        except Exception as e:
            return "I can't get that for you right now."
