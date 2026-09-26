import duckdb
from pathlib import Path

INPUT = "data/processed/v3/overture_canada_classified.parquet"
OUTPUT = "data/processed/v3/overture_business_candidates_v2.parquet"

Path("data/processed/v3").mkdir(parents=True, exist_ok=True)

# Explicit commercial / operating-business categories.
BUSINESS = {
    "home_service",
    "restaurant",
    "personal_or_beauty_service",
    "real_estate_service",
    "financial_service",
    "automotive_service",
    "hardware_home_and_garden_store",
    "professional_service",
    "fashion_and_apparel_store",
    "food_and_beverage_store",
    "wellness_service",
    "casual_eatery",
    "dental_clinic",
    "manufacturer",
    "sport_or_fitness_facility",
    "corporate_or_business_office",
    "complementary_and_alternative_medicine",
    "animal_or_pet_service",
    "technical_service",
    "auto_dealer",
    "pharmacy_and_drug_store",
    "building_or_construction_service",
    "bank_or_credit_union",
    "attorney_or_law_firm",
    "gas_station",
    "shopping",
    "shipping_or_delivery_service",
    "coffee_shop",
    "event_or_party_service",
    "b2b_service",
    "hotel",
    "travel_service",
    "convenience_store",
    "flowers_and_gifts_store",
    "fast_food_restaurant",
    "gym",
    "media_service",
    "electronics_store",
    "farm",
    "behavioral_or_mental_health_clinic",
    "sporting_goods_store",
    "bar",
    "specialty_store",
    "design_service",
    "lodging",
    "rental_service",
    "physical_medicine_and_rehabilitation",
    "supplier_or_distributor",
    "cafe",
    "printing_service",
    "arts_crafts_and_hobby_store",
    "b2b_transportation_and_storage_service",
    "second_hand_store",
    "senior_living_facility",
    "storage_facility",
    "vehicle_parts_store",
    "medical_service",
    "diagnostics_imaging_or_lab_service",
    "animal_and_pet_store",
    "specialized_health_care",
    "vision_or_eye_care_clinic",
    "books_music_and_video_store",
    "art_gallery",
    "b2b_office_and_professional_service",
    "ev_charging_station",
    "hospital",
    "health_care",
    "fitness_studio",
    "vehicle_dealer",
    "music_venue",
    "outpatient_care_facility",
    "personal_care_and_beauty_store",
    "bed_and_breakfast",
    "legal_service",
    "laundry_service",
    "golf_course",
    "environmental_or_ecological_service",
    "tutoring_service",
    "discount_store",
    "private_lodging",
    "farmers_market",
    "b2b_energy_and_utility_service",
    "shopping_mall",
    "department_store",
    "b2b_industrial_and_machine_service",
    "primary_care_or_general_clinic",
    "non_alcoholic_beverage_venue",
    "fueling_station",
    "warehouse_club_store",
    "telecommunications_service",
    "food_service",
    "resort",
    "brewery",
    "wholesaler",
    "agricultural_service",
    "taxi_or_ride_share_service",
    "vehicle_service",
    "smoothie_juice_bar",
    "winery",
    "office_supply_store",
    "movie_theater",
    "toys_and_games_store",
    "theatre_venue",
    "recreational_equipment_rental",
    "musical_instrument_and_pro_audio_store",
    "lounge",
    "food_truck_stand",
    "marina",
    "dance_club",
    "radio_station",
    "reproductive_perinatal_and_womens_care",
    "surgery",
    "specialized_medical_facility",
    "event_venue",
    "amusement_park",
    "performing_arts_venue",
    "security_service",
    "psychic_advising",
    "arcade",
    "emergency_or_urgent_care_facility",
    "industrial_facility_or_service",
    "b2b_science_and_technology_service",
    "distillery",
    "casino",
    "walk_in_clinic",
    "market",
    "housing_or_property_service",
    "comedy_club",
    "adult_entertainment_venue",
    "amusement_attraction",
    "astrological_advising",
    "pediatric_clinic",
    "nightlife_venue",
    "superstore",
    "arts_and_crafts_space",
    "alcoholic_beverage_venue",
    "food_court",
    "ticket_office_or_booth",
    "television_station",
    "urgent_care_clinic",
    "specialty_hospital",
    "country_club",
    "kiosk",
    "shopping_service",
    "makerspace",
}

# Clearly not commercial businesses for this B2B prospecting dataset.
NON_BUSINESS = {
    "lake",
    "historic_site",
    "christian_place_of_worship",
    "park",
    "river",
    "mountain",
    "government_office",
    "elementary_school",
    "civic_organization",
    "college_university",
    "community_center",
    "library",
    "community_and_government",
    "religious_organization",
    "museum",
    "youth_organization",
    "beach",
    "airport",
    "high_school",
    "geographic_entities",
    "public_utility",
    "stadium_arena",
    "preschool",
    "recreational_trail_or_path",
    "fire_station",
    "apartment",
    "train_station",
    "research_institute",
    "campus_building",
    "labor_union",
    "public_transit_facility_or_service",
    "police_station",
    "playground",
    "political_organization",
    "monument",
    "dog_park",
    "national_park",
    "bridge",
    "nature_reserve",
    "muslim_place_of_worship",
    "government_department",
    "embassy",
    "food_bank",
    "military_site",
    "courthouse",
    "public_plaza",
    "hindu_place_of_worship",
    "buddhist_place_of_worship",
    "jewish_place_of_worship",
    "island",
    "public_fountain",
    "waterfall",
    "place_of_worship",
    "lighthouse",
    "garden",
    "jail_or_prison",
    "sculpture_statue",
    "cemetery",
    "pier",
    "canal",
    "hot_springs",
    "public_restroom",
    "rest_stop",
    "fort",
    "land_feature",
    "built_feature",
    "street_art",
    "forest",
    "castle",
    "military_base",
    "memorial_site",
    "canyon",
}

con = duckdb.connect()

business_sql = ",".join("'" + x.replace("'", "''") + "'" for x in BUSINESS)
non_business_sql = ",".join("'" + x.replace("'", "''") + "'" for x in NON_BUSINESS)

con.execute(f"""
CREATE OR REPLACE TEMP TABLE audited AS
SELECT
    *,
    CASE
        WHEN operating_status_class = 'PERMANENTLY_CLOSED'
            THEN 'NON_BUSINESS'

        WHEN basic_category IN ({business_sql})
            THEN 'BUSINESS'

        WHEN basic_category IN ({non_business_sql})
            THEN 'NON_BUSINESS'

        ELSE 'REVIEW'
    END AS audited_classification
FROM read_parquet('{INPUT}')
""")

print("\n=== STRICT CANADA CLASSIFICATION ===\n")

rows = con.execute("""
SELECT
    audited_classification,
    COUNT(*) AS records,
    COUNT(phone) AS phone,
    COUNT(email) AS email,
    COUNT(website) AS website,
    ROUND(AVG(confidence), 3) AS avg_confidence
FROM audited
GROUP BY audited_classification
ORDER BY records DESC
""").fetchall()

for row in rows:
    print(
        f"{row[0]:15} "
        f"Records: {row[1]:,} | "
        f"Phone: {row[2]:,} | "
        f"Email: {row[3]:,} | "
        f"Website: {row[4]:,} | "
        f"Avg confidence: {row[5]}"
    )

print("\n=== REVIEW CATEGORIES ===\n")

review = con.execute("""
SELECT basic_category, COUNT(*) AS n
FROM audited
WHERE audited_classification = 'REVIEW'
GROUP BY basic_category
ORDER BY n DESC
""").fetchall()

for category, count in review:
    print(f"{str(category):50} {count:,}")

con.execute(f"""
COPY (
    SELECT *
    FROM audited
    WHERE audited_classification = 'BUSINESS'
)
TO '{OUTPUT}'
(FORMAT PARQUET, COMPRESSION ZSTD)
""")

print(f"\nSaved business candidates: {OUTPUT}")
print("DONE")