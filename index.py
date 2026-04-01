from http.server import BaseHTTPRequestHandler
import json
import requests
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import os
import time
import phonenumbers
from phonenumbers import (
    geocoder, carrier, number_type, timezone,
    is_valid_number, is_possible_number,
    region_code_for_number,
    PhoneNumberFormat, format_number
)


class handler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def load_keys(self):
        try:
            path = os.path.join(os.path.dirname(__file__), "..", "keys.json")
            with open(path, "r") as f:
                return json.load(f)
        except:
            return {}

    def validate_key(self, api_key):
        keys = self.load_keys()

        if api_key not in keys:
            return False, "invalid key"

        key_data = keys[api_key]

        if not key_data.get("active"):
            return False, "key disabled"

        expires_at = key_data.get("expires_at")

        if expires_at:
            expiry_time = datetime.fromisoformat(expires_at)
            if datetime.utcnow() > expiry_time:
                return False, "key expired"

        return True, "valid"

    # Hard Fetch with retry
    def hard_fetch(self, url, retries=3):
        for _ in range(retries):
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    return r.json()
            except:
                time.sleep(1)
        return None

    # ─────────────────────────────────────────────────────────────
    #  PHONE ANALYSIS FUNCTIONS
    # ─────────────────────────────────────────────────────────────

    def get_phone_type_str(self, t):
        return {
            0:  "Fixed Line",
            1:  "Mobile",
            2:  "Fixed Line / Mobile",
            3:  "Toll Free",
            4:  "Premium Rate",
            5:  "Shared Cost",
            6:  "VoIP",
            7:  "Personal Number",
            8:  "Pager",
            9:  "UAN",
            10: "Voicemail",
            27: "Unknown"
        }.get(t, "Unknown")

    def get_sim_type(self, t):
        if t == 1:
            return "Likely Prepaid (Mobile)"
        if t == 0:
            return "Likely Postpaid (Fixed Line)"
        if t == 6:
            return "VoIP / Internet"
        return "Cannot Determine"

    def get_call_type(self, parsed):
        return "Domestic (Local / STD)" if parsed.country_code == 91 else "International (ISD)"

    def get_region(self, parsed, national_num):
        """
        India --> prefix-based state map (accurate)
        Others --> phonenumbers geocoder (city/region where available)
        """
        if parsed.country_code == 91:
            return self.get_india_state(national_num)
        geo = geocoder.description_for_number(parsed, "en")
        return geo.strip() if geo and geo.strip() else "Not Available"

    def get_india_state(self, n):
        p = n[:4]
        m = {
            # Delhi
            "9810": "Delhi", "9811": "Delhi", "9871": "Delhi",
            "9870": "Delhi", "9910": "Delhi", "9990": "Delhi",
            "9999": "Delhi", "9540": "Delhi", "8800": "Delhi",
            "7011": "Delhi", "7042": "Delhi", "7043": "Delhi",
            "7044": "Delhi", "7045": "Delhi", "9312": "Delhi",
            "9717": "Delhi", "9716": "Delhi", "9313": "Delhi",
            # Maharashtra
            "9820": "Maharashtra", "9821": "Maharashtra", "9822": "Maharashtra",
            "9823": "Maharashtra", "9850": "Maharashtra", "9860": "Maharashtra",
            "9890": "Maharashtra", "9920": "Maharashtra", "9930": "Maharashtra",
            "9960": "Maharashtra", "9970": "Maharashtra", "9503": "Maharashtra",
            "9527": "Maharashtra", "9545": "Maharashtra", "7020": "Maharashtra",
            "7021": "Maharashtra", "8390": "Maharashtra", "9167": "Maharashtra",
            "9004": "Maharashtra", "9326": "Maharashtra", "9373": "Maharashtra",
            # Karnataka
            "9845": "Karnataka", "9880": "Karnataka", "9900": "Karnataka",
            "9980": "Karnataka", "9448": "Karnataka", "9449": "Karnataka",
            "9480": "Karnataka", "9481": "Karnataka", "9482": "Karnataka",
            "9513": "Karnataka", "9535": "Karnataka", "6360": "Karnataka",
            "7022": "Karnataka", "8050": "Karnataka", "9972": "Karnataka",
            "9886": "Karnataka", "9342": "Karnataka", "7019": "Karnataka",
            # Tamil Nadu
            "9840": "Tamil Nadu", "9940": "Tamil Nadu", "9443": "Tamil Nadu",
            "9500": "Tamil Nadu", "9514": "Tamil Nadu", "9515": "Tamil Nadu",
            "9543": "Tamil Nadu", "6380": "Tamil Nadu", "7010": "Tamil Nadu",
            "8300": "Tamil Nadu", "9444": "Tamil Nadu", "9952": "Tamil Nadu",
            "9361": "Tamil Nadu", "9894": "Tamil Nadu", "8124": "Tamil Nadu",
            # Kerala
            "9400": "Kerala", "9446": "Kerala", "9447": "Kerala",
            "9495": "Kerala", "9496": "Kerala", "9539": "Kerala",
            "9544": "Kerala", "9895": "Kerala", "8281": "Kerala",
            "9387": "Kerala", "7994": "Kerala", "8086": "Kerala", "9048": "Kerala",
            # Uttar Pradesh
            "9801": "Uttar Pradesh", "9450": "Uttar Pradesh", "9451": "Uttar Pradesh",
            "9452": "Uttar Pradesh", "9506": "Uttar Pradesh", "9511": "Uttar Pradesh",
            "9516": "Uttar Pradesh", "9517": "Uttar Pradesh", "9518": "Uttar Pradesh",
            "9519": "Uttar Pradesh", "9520": "Uttar Pradesh", "9521": "Uttar Pradesh",
            "9522": "Uttar Pradesh", "9523": "Uttar Pradesh", "9528": "Uttar Pradesh",
            "9532": "Uttar Pradesh", "9536": "Uttar Pradesh", "9538": "Uttar Pradesh",
            "9548": "Uttar Pradesh", "9455": "Uttar Pradesh", "9415": "Uttar Pradesh",
            # Rajasthan
            "9950": "Rajasthan", "9460": "Rajasthan", "9461": "Rajasthan",
            "9462": "Rajasthan", "9504": "Rajasthan", "9509": "Rajasthan",
            "9524": "Rajasthan", "9529": "Rajasthan", "9530": "Rajasthan",
            "9531": "Rajasthan", "9549": "Rajasthan",
            # Gujarat
            "9510": "Gujarat", "9512": "Gujarat", "9537": "Gujarat",
            "7600": "Gujarat", "8000": "Gujarat", "8200": "Gujarat",
            "9099": "Gujarat", "9898": "Gujarat", "9427": "Gujarat",
            "9909": "Gujarat", "9824": "Gujarat", "9825": "Gujarat",
            "9979": "Gujarat", "8140": "Gujarat",
            # Punjab
            "9803": "Punjab", "9876": "Punjab", "9501": "Punjab",
            "7700": "Punjab", "9779": "Punjab", "9814": "Punjab",
            "9815": "Punjab", "9417": "Punjab", "8146": "Punjab",
            "9878": "Punjab", "7087": "Punjab",
            # West Bengal
            "9800": "West Bengal", "9830": "West Bengal", "9474": "West Bengal",
            "9475": "West Bengal", "9547": "West Bengal", "7001": "West Bengal",
            "8100": "West Bengal", "9433": "West Bengal", "9831": "West Bengal",
            "8697": "West Bengal",
        }
        return m.get(p, "Not Available")

    def check_whatsapp(self, e164):
        """Check WhatsApp registration"""
        try:
            clean = e164.replace("+", "")
            r = requests.get(
                f"https://wa.me/{clean}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
                allow_redirects=True
            )
            content = r.text.lower()

            not_registered = [
                "phone number shared via link is not",
                "number is not registered",
                "invalid phone number",
                "this phone number is not on whatsapp",
                "not on whatsapp",
            ]

            for sig in not_registered:
                if sig in content:
                    return "Not Registered"

            return "Registered"
        except:
            return "Check Failed"

    def analyze_phone(self, number):
        """Main phone analysis function"""
        try:
            # Try to parse with default region if no country code
            if not number.startswith('+'):
                # Try to detect if it's Indian number (10 digits)
                if len(number) == 10 and number.isdigit():
                    parsed = phonenumbers.parse(number, "IN")
                else:
                    parsed = phonenumbers.parse(number, None)
            else:
                parsed = phonenumbers.parse(number, None)
                
        except phonenumbers.phonenumberutil.NumberParseException as e:
            return {
                "status": False,
                "msg": f"Cannot parse number: {str(e)}",
                "error": "Invalid number format"
            }

        if not is_valid_number(parsed):
            return {
                "status": False,
                "msg": "Invalid phone number. Check the number and country code.",
                "error": "Invalid number"
            }

        # Extract all data
        country = geocoder.description_for_number(parsed, "en") or "Not Available"
        sim_carrier = carrier.name_for_number(parsed, "en") or "Not Available"
        sim_type_int = number_type(parsed)
        time_zones = timezone.time_zones_for_number(parsed)
        country_code = parsed.country_code
        national_num = str(parsed.national_number)
        region_code = region_code_for_number(parsed)
        possible = is_possible_number(parsed)

        # Number formats
        intl_fmt = format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
        natl_fmt = format_number(parsed, PhoneNumberFormat.NATIONAL)
        e164_fmt = format_number(parsed, PhoneNumberFormat.E164)
        rfc_fmt = format_number(parsed, PhoneNumberFormat.RFC3966)

        # Derived info
        region_area = self.get_region(parsed, national_num)
        phone_type = self.get_phone_type_str(sim_type_int)
        sim_type_str = self.get_sim_type(sim_type_int)
        call_type = self.get_call_type(parsed)
        is_mobile = sim_type_int == 1
        is_tollfree = sim_type_int == 3
        is_voip = sim_type_int == 6

        # WhatsApp check
        wa_status = self.check_whatsapp(e164_fmt)

        # Construct result data
        data = {
            "identification": {
                "international": intl_fmt,
                "national_format": natl_fmt,
                "e164_format": e164_fmt,
                "rfc3966_format": rfc_fmt,
                "valid_number": "Yes",
                "possible_number": "Yes" if possible else "No"
            },
            "location": {
                "country": country,
                "region_state": region_area,
                "country_code": f"+{country_code}",
                "region_code": region_code,
                "time_zone": ', '.join(time_zones) if time_zones else "Not Available"
            },
            "carrier_line": {
                "carrier": sim_carrier,
                "phone_type": phone_type,
                "sim_category": sim_type_str,
                "call_type": call_type,
                "mobile_number": "Yes" if is_mobile else "No",
                "toll_free": "Yes" if is_tollfree else "No",
                "voip_internet": "Yes" if is_voip else "No"
            },
            "number_details": {
                "number_length": f"{len(national_num)} digits",
                "area_code": national_num[:3] if len(national_num) >= 3 else national_num,
                "subscriber_no": national_num[3:] if len(national_num) > 3 else "",
                "prefix_4digit": national_num[:4] if len(national_num) >= 4 else national_num
            },
            "social_media": {
                "whatsapp": wa_status,
                "whatsapp_link": f"https://wa.me/{e164_fmt.replace('+', '')}"
            }
        }

        return {
            "status": True,
            "searched": number,
            "data": data,
            "developer": "@Cyb3rB4nn3r",
            "time": datetime.utcnow().isoformat()
        }

    # ─────────────────────────────────────────────────────────────
    #  API HANDLERS
    # ─────────────────────────────────────────────────────────────

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            # Check if it's a bypass request
            link = params.get("link", [None])[0]
            api_key = params.get("key", [None])[0]

            # Phone number lookup
            phone = params.get("phone", [None])[0]

            # API key validation
            if not api_key:
                return self.send_json({
                    "status": False,
                    "msg": "api key required",
                    "developer": "@Cyb3rB4nn3r",
                    "time": datetime.utcnow().isoformat()
                }, 403)

            valid, message = self.validate_key(api_key)
            if not valid:
                return self.send_json({
                    "status": False,
                    "msg": message,
                    "developer": "@Cyb3rB4nn3r",
                    "time": datetime.utcnow().isoformat()
                }, 403)

            # Handle phone number lookup
            if phone:
                result = self.analyze_phone(phone)
                if result["status"]:
                    return self.send_json(result)
                else:
                    return self.send_json(result, 400)

            # Handle link bypass
            elif link:
                external_url = f"https://l1nk-by9ass-4pi.onrender.com/bypass?link={link}"
                data = self.hard_fetch(external_url)

                if not data:
                    return self.send_json({
                        "status": False,
                        "msg": "bypass failed",
                        "developer": "@Cyb3rB4nn3r",
                        "time": datetime.utcnow().isoformat()
                    })

                bypass_link = data.get("bypass")
                if bypass_link and bypass_link.startswith("//"):
                    bypass_link = bypass_link.replace("//", "", 1)

                result = {
                    "cached": data.get("cached"),
                    "original": data.get("original"),
                    "bypass": bypass_link,
                    "usage_count": data.get("usage_count"),
                    "developer": "@Cyb3rB4nn3r",
                    "time": datetime.utcnow().isoformat()
                }
                return self.send_json(result)

            else:
                return self.send_json({
                    "status": False,
                    "msg": "Either 'phone' or 'link' parameter required",
                    "developer": "@Cyb3rB4nn3r",
                    "time": datetime.utcnow().isoformat()
                }, 400)

        except Exception as e:
            return self.send_json({
                "status": False,
                "msg": "server error",
                "error": str(e),
                "developer": "@Cyb3rB4nn3r",
                "time": datetime.utcnow().isoformat()
            }, 500)
