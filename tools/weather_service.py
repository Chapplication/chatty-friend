from .llm_tool_base import LLMTool, LLMToolParameter

from datetime import datetime
from collections import defaultdict

import re

import re

def replace_numbers_with_words(text):
    """
    Replace integers under 200 with their spelled-out equivalents in the given text.
    Also converts MM/DD date patterns to spelled-out format.
    
    Args:
        text (str): Input text containing numbers to replace
        
    Returns:
        str: Text with numbers replaced by words
    """
    # Define number-to-word mappings
    ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
    teens = ['ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 
             'sixteen', 'seventeen', 'eighteen', 'nineteen']
    tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
    
    # Month names
    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    
    def num_to_word(n):
        """Convert a single number to its word representation."""
        n = int(n)
        if n == 0:
            return 'zero'
        elif n < 10:
            return ones[n]
        elif n < 20:
            return teens[n - 10]
        elif n < 100:
            return tens[n // 10] + ('-' + ones[n % 10] if n % 10 else '')
        elif n < 200:
            return 'one hundred' + (' ' + num_to_word(n - 100) if n > 100 else '')
        else:
            return str(n)  # Return as-is if >= 200
    
    def date_to_words(match):
        """Convert MM/DD pattern to spelled-out date format."""
        month_num = int(match.group(1))
        day_num = int(match.group(2))
        
        # Convert day to ordinal form
        day_word = num_to_word(day_num)
        
        # Add ordinal suffix
        if day_num == 1 or day_num == 21 or day_num == 31:
            day_ordinal = day_word + ' first'
        elif day_num == 2 or day_num == 22:
            day_ordinal = day_word.replace('two', 'second') if day_num == 2 else day_word.replace('two', 'second')
        elif day_num == 3 or day_num == 23:
            day_ordinal = day_word.replace('three', 'third') if day_num == 3 else day_word.replace('three', 'third')
        else:
            if 11 <= day_num <= 13:
                day_ordinal = day_word + 'th'
            elif day_num % 10 == 1:
                day_ordinal = day_word + 'st'
            elif day_num % 10 == 2:
                day_ordinal = day_word + 'nd'
            elif day_num % 10 == 3:
                day_ordinal = day_word + 'rd'
            else:
                day_ordinal = day_word + 'th'
        
        # Get month name
        month_name = months[month_num] if 1 <= month_num <= 12 else f"month {month_num}"
        
        return f"{month_name} {day_ordinal}"
    
    def replace_regular_number(match):
        """Replace a matched number with its word equivalent."""
        num_str = match.group()
        return num_to_word(num_str)
    
    # First, replace date patterns MM/DD
    result = re.sub(r'\b(\d{1,2})/(\d{1,2})\b', date_to_words, text)
    
    # Then replace remaining standalone numbers
    result = re.sub(r'\b\d{1,3}\b', replace_regular_number, result)
    
    return result


def summarize_weather_forecast(forecast_data):
    """
    Generate natural language sentences about weather conditions for up to 5 days.
    
    Args:
        forecast_data: List of weather forecast dictionaries
        
    Returns:
        str: Natural language summary of the weather forecast
    """
    # Group data by date
    daily_data = defaultdict(list)
    
    for entry in forecast_data:
        # Convert timestamp to date
        date = datetime.fromtimestamp(entry['dt']).date()
        daily_data[date].append(entry)
    
    # Sort dates and limit to 5 days
    sorted_dates = sorted(daily_data.keys())[:5]
    
    summaries = []
    
    for date in sorted_dates:
        day_entries = daily_data[date]
        
        # Calculate daily averages and conditions
        temps = [entry['main']['temp'] for entry in day_entries]
        humidities = [entry['main']['humidity'] for entry in day_entries]
        
        # Count weather conditions
        conditions = {}
        for entry in day_entries:
            weather_main = entry['weather'][0]['main']
            conditions[weather_main] = conditions.get(weather_main, 0) + 1
        
        # Calculate averages
        avg_temp = sum(temps) / len(temps)
        avg_humidity = sum(humidities) / len(humidities)
        min_temp = min(temps)
        max_temp = max(temps)
        
        # Determine dominant weather condition
        dominant_condition = max(conditions.items(), key=lambda x: x[1])[0]
        
        # Format date
        day_name = date.strftime("%A, %B %d")
        
        # Build summary sentence
        summary = f"{day_name}: "
        
        # Temperature description
        summary += f"Temperatures will range from {min_temp:.0f}°F to {max_temp:.0f}°F (avg {avg_temp:.0f}°F). "
        
        # Weather condition description
        if dominant_condition == "Clear":
            summary += "Expect mostly sunny skies"
        elif dominant_condition == "Clouds":
            cloud_percentage = (conditions.get("Clouds", 0) / len(day_entries)) * 100
            if cloud_percentage > 75:
                summary += "It will be mostly cloudy"
            else:
                summary += "Expect partly cloudy conditions"
        elif dominant_condition == "Rain":
            summary += "Rain is expected"
        else:
            summary += f"{dominant_condition} conditions expected"
        
        # Humidity description
        if avg_humidity > 80:
            summary += f" with high humidity around {avg_humidity:.0f}%"
        elif avg_humidity > 60:
            summary += f" with moderate humidity around {avg_humidity:.0f}%"
        else:
            summary += f" with comfortable humidity levels around {avg_humidity:.0f}%"
        
        summary += "."
        summaries.append(summary)
    
    return "\n\n".join(summaries)


# Alternative simplified version
def quick_weather_summary(forecast_data):
    """
    Quick one-liner summaries for each day.
    
    Args:
        forecast_data: List of weather forecast dictionaries
        
    Returns:
        str: Brief summary of weather forecast
    """
    daily_data = defaultdict(list)
    
    for entry in forecast_data:
        date = datetime.fromtimestamp(entry['dt']).strftime("%a %m/%d")
        daily_data[date].append(entry)
    
    summaries = []
    dates = list(daily_data.keys())[:5]
    
    for date in dates:
        day_entries = daily_data[date]
        
        # Quick calculations
        temps = [e['main']['temp'] for e in day_entries]
        avg_temp = sum(temps) / len(temps)
        avg_humidity = sum(e['main']['humidity'] for e in day_entries) / len(day_entries)
        
        # Count main weather types
        weather_types = [e['weather'][0]['main'] for e in day_entries]
        main_weather = max(set(weather_types), key=weather_types.count)
        
        # Simple description
        if main_weather == "Clear":
            weather_desc = "sunny"
        elif main_weather == "Clouds":
            weather_desc = "cloudy"
        elif main_weather == "Rain":
            weather_desc = "rainy"
        else:
            weather_desc = main_weather.lower()
        
        summary = f"{date}: {avg_temp:.0f}°F, {weather_desc}, {avg_humidity:.0f}% humidity"
        summaries.append(summary)
    
    return "\n".join(summaries)


class WeatherService(LLMTool):
    def __init__(self, master_state):
        weather_city = LLMToolParameter("weather_city","City name, state code and country code divided by commas for the location where weather is requested.  Country code uses ISO 3166-1 alpha-2 format. Use context or ask user if no city mentioned.", required=True)
        request_type = LLMToolParameter("request_type","Type of weather information: 'current' for current conditions or 'forecast' for 5-day forecast", enum=["current", "forecast"], required=True)
        detail_level = LLMToolParameter("detail_level","Level of detail for weather report: 'quick' for brief summary or 'detailed' for full information", enum=["quick", "detailed"], required=False)
        super().__init__("weather_service","Get current weather conditions or 5-day forecast for any city worldwide using OpenWeatherMap API.", [weather_city,request_type,detail_level], master_state)
        
        # Load API key from configuration with fallback
        self.weather_api_key = self.get_api_key()
        self.request_timeout = 10  # seconds
        self.max_retries = 2

    def get_api_key(self):
        """Get weather API key from secrets manager"""
        api_key = self.master_state.secrets_manager.get_secret('openweather_api_key')
        if api_key:
            return api_key

    def can_invoke(self):
        return self.get_api_key() is not None

    def make_api_request(self, url):
        """Make API request with proper error handling and retries"""
        import requests
        from requests.exceptions import ConnectionError, Timeout, RequestException
        
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(url, timeout=self.request_timeout)
                return response, None
                
            except ConnectionError:
                if attempt == self.max_retries:
                    return None, "Unable to connect to weather service. Please check your internet connection."
                continue
                
            except Timeout:
                if attempt == self.max_retries:
                    return None, "Weather service request timed out. Please try again later."
                continue
                
            except RequestException as e:
                return None, f"Weather service error: {str(e)}"
        
        return None, "Weather service temporarily unavailable after multiple attempts."

    def parse_api_response(self, response):
        """Parse API response with comprehensive error handling"""
        # Check HTTP status codes
        if response.status_code == 401:
            return None, "Weather service authentication failed. Please contact administrator."
        elif response.status_code == 404:
            return None, "City not found. Please check the spelling or try including state/country (e.g., 'Paris, France')."
        elif response.status_code == 429:
            return None, "Weather service quota exceeded. Please try again later."
        elif response.status_code != 200:
            return None, f"Weather service error (code {response.status_code}). Please try again later."
        
        # Parse JSON response
        try:
            data = response.json()
            return data, None
        except ValueError as e:
            return None, "Weather service returned invalid data format. Please try again later."

    def safe_get_nested(self, data, *keys, default=None):
        """Safely get nested dictionary values"""
        try:
            result = data
            for key in keys:
                if isinstance(result, dict) and key in result:
                    result = result[key]
                elif isinstance(result, list) and isinstance(key, int) and 0 <= key < len(result):
                    result = result[key]
                else:
                    return default
            return result
        except (TypeError, KeyError, IndexError):
            return default

    def format_current_weather(self, weather_data, detail_level="quick"):
        """Format current weather data with safe data access"""
        try:
            # Extract data safely
            temp = self.safe_get_nested(weather_data, 'main', 'temp')
            feels_like = self.safe_get_nested(weather_data, 'main', 'feels_like')
            humidity = self.safe_get_nested(weather_data, 'main', 'humidity')
            weather_desc = self.safe_get_nested(weather_data, 'weather', 0, 'description')
            city_name = self.safe_get_nested(weather_data, 'name')
            
            if temp is None:
                return "Weather data is incomplete. Please try again."
            
            # Build response based on detail level
            if detail_level == "quick":
                # Quick format: "City: 72°F, sunny"
                response = f"{city_name or 'Location'}: {int(round(temp))}°F"
                if weather_desc:
                    response += f", {weather_desc}"
                return response
            else:
                # Detailed format (original behavior)
                response = f"Current weather in {city_name or 'the requested location'}:\n"
                response += f"Temperature: {int(round(temp))}°F"
                
                if feels_like is not None and abs(feels_like - temp) > 3:
                    response += f" (feels like {int(round(feels_like))}°F)"
                
                if weather_desc:
                    response += f"\nConditions: {weather_desc.title()}"
                
                if humidity is not None:
                    response += f"\nHumidity: {humidity}%"
                
                return response
            
        except Exception as e:
            return f"Error formatting weather data: {str(e)}"

    def format_forecast_weather(self, forecast_data, detail_level="quick"):
        """Format forecast data with safe data access and improved logic"""
        try:
            forecast_list = self.safe_get_nested(forecast_data, 'list', default=[])
            if not forecast_list:
                return "Forecast data is not available. Please try again."
            
            response = None
            if detail_level == "quick":
                response = quick_weather_summary(forecast_list)
            else:
                response = summarize_weather_forecast(forecast_list)

            return "Format the following information as a "+detail_level+" weather forecast: "+ response
            
        except Exception as e:
            return f"Can't get forecast. Error formatting forecast data: {str(e)}"

    async def invoke(self, args):
        """Main weather service invocation with comprehensive error handling"""
        try:
            # Validate API key
            if not self.weather_api_key:
                return "Weather service is not configured. Please contact administrator."
            
            # Validate inputs
            weather_city = args.get("weather_city", "").strip().lower().replace(" ", "%20")
            request_type = args.get("request_type", "current").lower().strip()
            detail_level = args.get("detail_level", "quick").lower().strip()
            
            # Validate city input
            # Validate request type
            if request_type not in ["current", "forecast"]:
                request_type = "current"  # Default fallback
            
            # Validate detail level
            if detail_level not in ["quick", "detailed"]:
                detail_level = "quick"  
            
            # Build API URL
            base_url = "https://api.openweathermap.org/data/2.5"
            if request_type == "forecast":
                url = f"{base_url}/forecast?q={weather_city}&units=imperial&cnt=40&appid={self.weather_api_key}"
            else:
                url = f"{base_url}/weather?q={weather_city}&units=imperial&appid={self.weather_api_key}"
            
            # Make API request
            response, request_error = self.make_api_request(url)
            if request_error:
                return request_error
            
            # Parse API response
            weather_data, parse_error = self.parse_api_response(response)
            if parse_error:
                return parse_error
            
            # Format and return weather information
            if request_type == "forecast":
                ret = self.format_forecast_weather(weather_data, detail_level)
            else:
                ret = self.format_current_weather(weather_data, detail_level)

            return replace_numbers_with_words(ret)
                
        except Exception as e:
            return f"Weather service encountered an unexpected error: {str(e)}. Please try again or contact support."