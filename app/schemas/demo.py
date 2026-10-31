from typing import Literal

from pydantic import BaseModel


class DemoInfo(BaseModel):
    demo_mode: Literal[True] = True
    banner: str = "TruStay demo - sample inspection workflows and simulated payments."
    payment_mode: Literal['simulated'] = 'simulated'
    payment_notice: str = "Payments, fees, refunds and payouts are database records only. No real money is collected or transferred."
    login_mode: Literal['development_otp', 'sms_not_configured']
    login_notice: str
    inspection_notice: str = "Inspection content is for demonstration. Sample notes and photos are not proof of a completed real-world inspection."
    ai_notice: str = "Initial AI verification checks report notes only. Photos are sent to AI after renter rejection. Configured AI calls may incur real provider charges."
