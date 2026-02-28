"""
Seed Data Generator for Booking Module
=======================================
Creates sample booking items for testing
Run this after Phase 1 implementation
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime
from booking_module import BookingItem

async def seed_booking_data():
    """Populate booking_items collection with sample data"""
    
    client = AsyncIOMotorClient(os.getenv('MONGO_URL', 'mongodb://localhost:27017'))
    db = client[os.getenv('DB_NAME', 'aventaro')]
    
    # Sample Hotels
    hotels = [
        BookingItem(
            service_type="hotel",
            provider_id="MMT_H001",
            provider_name="MakeMyTrip",
            name="The Grand Oberoi Mumbai",
            description="Luxury 5-star hotel with ocean views, infinity pool, and world-class dining",
            location="Marine Drive, Mumbai",
            check_in_date="2026-04-01",
            check_out_date="2026-04-05",
            price=15000.0,
            currency="INR",
            original_price=20000.0,
            commission_rate=10.0,
            images=["https://via.placeholder.com/800x600?text=Oberoi+Mumbai"],
            amenities=["WiFi", "Pool", "Gym", "Spa", "Restaurant", "Bar", "Room Service"],
            rating=4.8,
            reviews_count=2453,
            cancellation_policy="Free cancellation up to 48 hours before check-in",
            refund_policy="Full refund if cancelled 48+ hours before. 50% refund within 24-48 hours."
        ),
        BookingItem(
            service_type="hotel",
            provider_id="BKG_H002",
            provider_name="Booking.com",
            name="Taj Palace New Delhi",
            description="Historic luxury hotel near India Gate with award-winning restaurants",
            location="Sardar Patel Marg, New Delhi",
            check_in_date="2026-05-10",
            check_out_date="2026-05-15",
            price=12000.0,
            currency="INR",
            commission_rate=12.0,
            images=["https://via.placeholder.com/800x600?text=Taj+Palace"],
            amenities=["WiFi", "Pool", "Gym", "Spa", "Restaurant", "Concierge"],
            rating=4.7,
            reviews_count=1876,
            cancellation_policy="Free cancellation up to 72 hours before check-in"
        )
    ]
    
    # Sample Flights
    flights = [
        BookingItem(
            service_type="flight",
            provider_id="AI_F001",
            provider_name="Air India",
            name="AI-101 Mumbai to Delhi",
            description="Non-stop flight, Business Class",
            origin="Mumbai (BOM)",
            destination="Delhi (DEL)",
            departure_time="2026-04-15 08:00",
            arrival_time="2026-04-15 10:30",
            duration="2h 30m",
            price=8500.0,
            currency="INR",
            commission_rate=8.0,
            images=["https://via.placeholder.com/800x600?text=Air+India"],
            amenities=["Meals", "WiFi", "Entertainment", "Priority Boarding"],
            rating=4.2,
            reviews_count=542
        )
    ]
    
    # Sample Villas
    villas = [
        BookingItem(
            service_type="villa",
            provider_id="AIRBNB_V001",
            provider_name="Airbnb",
            name="Beachfront Villa Goa",
            description="3 BHK luxury villa with private pool and beach access",
            location="Candolim Beach, Goa",
            check_in_date="2026-06-01",
            check_out_date="2026-06-07",
            price=25000.0,
            currency="INR",
            commission_rate=15.0,
            images=["https://via.placeholder.com/800x600?text=Goa+Villa"],
            amenities=["Private Pool", "Beach Access", "Kitchen", "WiFi", "BBQ", "Parking"],
            rating=4.9,
            reviews_count=89,
            cancellation_policy="Full refund if cancelled 7+ days before check-in"
        )
    ]
    
    # Sample Cabs
    cabs = [
        BookingItem(
            service_type="airport_cab",
            provider_id="OLA_C001",
            provider_name="Ola Cabs",
            name="Mumbai Airport Transfer",
            description="Premium sedan with professional driver",
            origin="Mumbai Airport (BOM)",
            destination="Colaba, Mumbai",
            duration="45 mins",
            price=1200.0,
            currency="INR",
            commission_rate=20.0,
            amenities=["AC", "WiFi", "Child Seat Available"],
            rating=4.3,
            reviews_count=1234
        )
    ]
    
    # Sample Buses
    buses = [
        BookingItem(
            service_type="bus",
            provider_id="REDBUS_B001",
            provider_name="RedBus",
            name="Mumbai to Pune AC Sleeper",
            description="Volvo AC sleeper bus with charging ports",
            origin="Mumbai Central",
            destination="Pune Station",
            departure_time="2026-04-20 22:00",
            arrival_time="2026-04-21 02:30",
            duration="4h 30m",
            price=800.0,
            currency="INR",
            commission_rate=10.0,
            amenities=["AC", "Sleeper", "Charging Ports", "WiFi", "Water Bottle"],
            rating=4.4,
            reviews_count=678
        )
    ]
    
    # Sample Activities
    activities = [
        BookingItem(
            service_type="activity",
            provider_id="KLOOK_A001",
            provider_name="Klook",
            name="Scuba Diving Experience - Andaman",
            description="Full day scuba diving with instructor, equipment included",
            location="Havelock Island, Andaman",
            departure_date="2026-07-10",
            duration="6 hours",
            price=5500.0,
            currency="INR",
            commission_rate=18.0,
            images=["https://via.placeholder.com/800x600?text=Scuba+Diving"],
            amenities=["Equipment", "Instructor", "Lunch", "Photos", "Transport"],
            rating=4.9,
            reviews_count=342,
            cancellation_policy="Free cancellation up to 24 hours before activity"
        )
    ]
    
    all_items = hotels + flights + villas + cabs + buses + activities
    
    # Insert all items
    for item in all_items:
        await db.booking_items.insert_one(item.dict())
    
    print(f"✅ Seeded {len(all_items)} booking items")
    print(f"   - Hotels: {len(hotels)}")
    print(f"   - Flights: {len(flights)}")
    print(f"   - Villas: {len(villas)}")
    print(f"   - Cabs: {len(cabs)}")
    print(f"   - Buses: {len(buses)}")
    print(f"   - Activities: {len(activities)}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_booking_data())
