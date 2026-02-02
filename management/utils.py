import io
import base64
from decimal import Decimal
from num2words import num2words
import qrcode


def amount_to_words(amount):
    """Convert amount to words in Indian Rupees"""
    try:
        amount = float(amount)
        # Get the integer part
        rupees = int(amount)
        paise = int(round((amount - rupees) * 100))
        
        rupees_words = num2words(rupees, lang='en_IN').title()
        
        if paise > 0:
            paise_words = num2words(paise, lang='en_IN').title()
            return f"Rupees {rupees_words} and {paise_words} Paise Only"
        else:
            return f"Rupees {rupees_words} Only"
    except:
        return "Invalid amount"


def generate_phonepe_qr(amount, phone_number=""):
    """Generate PhonePe UPI QR code"""
    try:
        # PhonePe UPI format: upi://pay?pa=<upi_id>&pn=<name>&am=<amount>&tn=<transaction_note>
        # For PhonePe, we'll use a simplified format
        amount_str = f"{float(amount):.2f}"
        
        # UPI string format
        upi_string = f"upi://pay?pa=j.rakesh8252@ybl&pn=Prathibha Computer & Hardware Services&am={amount_str}&tn=Invoice"
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5,
            border=2,
        )
        qr.add_data(upi_string)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None
