"""Generate ~500 synthetic ACME Industries customer-support traces.

Each trace contains:
  1. A root chain run  ("ACME Support")
  2. A child LLM run   ("ChatOpenAI")
  3. Optional tool runs (~40 % of traces get 1-2 tool calls)

Output: module2_traces.json  (flat list of runs consumable by upload_traces.py)
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Distribution
# ---------------------------------------------------------------------------
PRODUCT_DISTRIBUTION: list[tuple[str, int]] = [
    ("Anvils", 200),
    ("Rocket Skates", 90),
    ("Giant Magnets", 75),
    ("Portable Holes", 75),
    ("Earthquake Pills", 60),
]

# ---------------------------------------------------------------------------
# Random-variable pools
# ---------------------------------------------------------------------------
ORDER_PREFIX = "ACME"
STATES = [
    "California", "Texas", "New York", "Florida", "Illinois", "Ohio",
    "Georgia", "Pennsylvania", "North Carolina", "Michigan", "Arizona",
    "Washington", "Colorado", "Tennessee", "Oregon", "Nevada", "Utah",
    "Minnesota", "Virginia", "New Jersey",
]
CITIES = [
    "Phoenix", "Austin", "Denver", "Seattle", "Portland", "Miami",
    "Chicago", "Atlanta", "Nashville", "San Diego", "Tucson", "Dallas",
    "Charlotte", "Orlando", "Las Vegas", "Boise", "Reno", "Tampa",
    "Sacramento", "Albuquerque",
]
FIRST_NAMES = [
    "Wile E.", "Road", "Bugs", "Daffy", "Elmer", "Tweety", "Sylvester",
    "Yosemite", "Foghorn", "Marvin", "Pepé", "Speedy", "Tasmanian",
    "Porky", "Lola", "Granny", "Henery", "Witch", "Sam", "Gossamer",
    "Ralph", "Cecil", "Beaky", "Claude", "Hubie", "Bertie", "Sniffles",
    "Bosko", "Buddy", "Foxy",
]
LAST_NAMES = [
    "Coyote", "Runner", "Bunny", "Duck", "Fudd", "Bird", "Cat",
    "Sam", "Leghorn", "Martian", "Le Pew", "Gonzales", "Devil",
    "Pig", "Bunny", "Granny", "Hawk", "Hazel", "Sheepdog", "Monster",
    "Wolf", "Turtle", "Buzzard", "Cat", "Mouse", "Bertie", "Mouse",
    "Bosko", "Buddy", "Fox",
]
ANVIL_WEIGHTS = ["50 lb", "100 lb", "200 lb", "500 lb", "1000 lb", "1 ton"]
MAGNET_STRENGTHS = ["500 gauss", "1000 gauss", "2500 gauss", "5000 gauss", "10000 gauss"]
HOLE_SIZES = ['3 ft', '5 ft', '8 ft', '10 ft', '12 ft']
QUAKE_RATINGS = ["3.0", "4.5", "5.0", "6.5", "7.0", "8.0"]
SKATE_SPEEDS = ["50 mph", "100 mph", "200 mph", "500 mph", "Mach 1"]


def _order_id() -> str:
    return f"{ORDER_PREFIX}-{random.randint(100000, 999999)}"


def _name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _state() -> str:
    return random.choice(STATES)


def _city() -> str:
    return random.choice(CITIES)


# ---------------------------------------------------------------------------
# Template bank – questions + responses per product/subtopic
# ---------------------------------------------------------------------------
# Each entry: (question_template, response_template, tool_name_or_None)
# Templates may use {order_id}, {name}, {state}, {city}, {weight}, etc.

TEMPLATES: dict[str, dict[str, list[tuple[str, str, str | None]]]] = {
    # ── Anvils ──────────────────────────────────────────────────────────
    "Anvils": {
        "delivery/shipping": [
            (
                "When will my anvil order {order_id} arrive?",
                "Let me check order {order_id}. Your {weight} anvil is currently in transit and is expected to arrive in {city}, {state} within 3-5 business days. You'll receive a tracking update once it ships from our warehouse.",
                "lookup_order",
            ),
            (
                "I need to ship a {weight} anvil to {state}. What are the shipping costs?",
                "Shipping a {weight} anvil to {state} costs between $45 and $120 depending on the delivery speed you choose. Standard ground shipping takes 5-7 business days, while express delivery is 2-3 days. Would you like me to generate a shipping quote?",
                None,
            ),
            (
                "My anvil delivery to {city} was delayed. Order number {order_id}.",
                "I apologize for the delay on order {order_id}. Let me look into this. It appears the shipment was held at our distribution center due to weight verification. I've flagged it for priority handling, and you should see movement within 24 hours.",
                "lookup_order",
            ),
            (
                "Can I get expedited shipping on a {weight} anvil to {state}?",
                "Yes, we offer expedited shipping for anvils up to 500 lb. For your {weight} anvil to {state}, express delivery (2-3 business days) is available for an additional $35. Overnight shipping is available for anvils under 200 lb.",
                None,
            ),
            (
                "Do you deliver anvils internationally? I need one shipped to Canada.",
                "We do ship anvils internationally. Canadian deliveries typically take 7-10 business days. Please note that customs fees and duties apply, and the buyer is responsible for those charges. I can prepare a quote for you.",
                None,
            ),
            (
                "My {weight} anvil arrived damaged. The packaging was torn open. Order {order_id}.",
                "I'm sorry to hear that your {weight} anvil arrived damaged. I've pulled up order {order_id}. I'll file a shipping damage claim right away and arrange for a replacement to be sent. Could you send photos of the damage to our claims team at claims@acme.com?",
                "lookup_order",
            ),
            (
                "What's the estimated delivery time for a {weight} anvil to {city}, {state}?",
                "For a {weight} anvil shipping to {city}, {state}, standard delivery takes 5-7 business days. Heavier anvils (500 lb and above) may require freight shipping which can take 7-10 days. I can check exact availability for your area.",
                None,
            ),
            (
                "I need to change the delivery address on my anvil order {order_id}.",
                "Let me pull up order {order_id}. I can update the shipping address as long as the order hasn't shipped yet. What's the new delivery address?",
                "lookup_order",
            ),
            (
                "Is there free shipping on anvil orders over $500?",
                "Yes! Orders over $500 qualify for free standard ground shipping within the continental US. Your anvil order would qualify. Express and overnight upgrades are still available at a reduced rate.",
                None,
            ),
            (
                "I ordered two anvils but only one arrived. Order {order_id}.",
                "I see order {order_id} in our system. It looks like the second anvil was shipped separately due to weight limits. The second shipment is currently in transit and should arrive within 2 business days. I'll send you the tracking number.",
                "lookup_order",
            ),
        ],
        "warranty claims": [
            (
                "My {weight} anvil cracked after two months. Is this covered under warranty?",
                "ACME anvils come with a 5-year structural warranty. A crack after two months is definitely covered. I'll initiate a warranty claim for you. We'll send a replacement {weight} anvil and arrange pickup of the damaged one at no cost.",
                "query_product_database",
            ),
            (
                "How do I file a warranty claim for my anvil? Order {order_id}.",
                "To file a warranty claim for order {order_id}, I can start the process right here. I'll need a brief description of the issue and a photo if possible. ACME anvils carry a 5-year structural warranty and a 1-year cosmetic warranty.",
                "lookup_order",
            ),
            (
                "Does the warranty cover cosmetic damage to my anvil?",
                "ACME anvils have two warranty tiers: a 5-year structural warranty (cracks, breaks, deformation) and a 1-year cosmetic warranty (surface scratches, paint chipping). If your anvil is within the first year, cosmetic damage is covered.",
                "query_product_database",
            ),
            (
                "My anvil's surface coating is peeling off. I bought it 8 months ago.",
                "Since you purchased the anvil 8 months ago, the peeling coating is covered under our 1-year cosmetic warranty. I can arrange a refinishing service or a full replacement. Which would you prefer?",
                None,
            ),
            (
                "I lost my receipt but need to make a warranty claim on my anvil.",
                "No problem. If you purchased through your ACME account, I can look up the order by your name or email. Alternatively, the serial number on the bottom of the anvil links directly to the purchase record in our system.",
                None,
            ),
            (
                "Can I extend the warranty on my {weight} anvil?",
                "Yes, we offer an extended warranty program for anvils. You can add 3 or 5 additional years of structural coverage. For a {weight} anvil, the 3-year extension is $49 and the 5-year extension is $79. Would you like to add one?",
                "query_product_database",
            ),
            (
                "My warranty claim {order_id} has been pending for two weeks. What's the status?",
                "Let me check on claim {order_id}. I see it's in the review queue. I'll escalate this to our warranty team for immediate processing. You should hear back within 48 hours. I apologize for the delay.",
                "lookup_order",
            ),
            (
                "Does dropping my anvil void the warranty?",
                "Normal use, including accidental drops, does not void the structural warranty. However, intentional misuse (such as using the anvil as a projectile) is not covered. Standard wear and tear from regular blacksmithing or industrial use is fully covered.",
                None,
            ),
            (
                "I'd like to return my anvil for a refund instead of a warranty replacement.",
                "I understand. Our return policy allows full refunds within 30 days of purchase. After 30 days, warranty claims result in repair or replacement. If you're within the 30-day window, I can process a return. When did you purchase the anvil?",
                None,
            ),
            (
                "The anvil I received doesn't match the product description. It's the wrong color.",
                "I'm sorry about that. A color mismatch would fall under our satisfaction guarantee. I can arrange either an exchange for the correct color or a full refund. Could you share your order number so I can look into this?",
                None,
            ),
        ],
        "sizing/weight": [
            (
                "What sizes do your anvils come in?",
                "ACME anvils are available in 50 lb, 100 lb, 200 lb, 500 lb, and 1000 lb models, plus our industrial 1-ton variant. The most popular for general use is the 100 lb model. Would you like specifications for a particular size?",
                "query_product_database",
            ),
            (
                "I need an anvil for jewelry making. What size do you recommend?",
                "For jewelry making, I'd recommend our 50 lb anvil. It has a precision-ground face that's perfect for detailed metalwork, and the smaller size is ideal for bench-top use. It comes with a horn suitable for ring shaping.",
                "query_product_database",
            ),
            (
                "What are the dimensions of the {weight} anvil?",
                "The {weight} ACME anvil measures approximately 18 x 8 x 10 inches (L x W x H). The face is hardened to 55 HRC for durability. I can send you the full specification sheet if you'd like.",
                "query_product_database",
            ),
            (
                "Is the {weight} anvil suitable for blacksmithing?",
                "The {weight} anvil is a solid choice for blacksmithing. For most hobby and professional work, we recommend 100 lb or heavier. The {weight} model has a hardened face, a pritchel hole, and a hardy hole. It should serve you well.",
                None,
            ),
            (
                "Can I get a custom-weight anvil?",
                "We do offer custom anvils for special orders. Weights from 25 lb up to 2 tons are available. Custom orders typically take 4-6 weeks for fabrication. I can connect you with our custom orders team for a quote.",
                None,
            ),
            (
                "What's the difference between your 200 lb and 500 lb anvils?",
                "The 500 lb model has a larger work surface (20 x 5 inches vs 16 x 4 inches), a wider horn, and includes both a pritchel and hardy hole. It's better for larger stock and heavier forging. The 200 lb is more versatile for general purpose work.",
                "query_product_database",
            ),
            (
                "How much does your lightest anvil weigh?",
                "Our lightest standard anvil is the 50 lb model. It's designed for bench work, jewelry making, and light metalworking. If you need something even lighter, we have a 25 lb travel anvil available as a special order.",
                None,
            ),
            (
                "I need an anvil that can fit through a standard doorway. What are my options?",
                "All our anvils up to 500 lb will fit through a standard 32-inch doorway. The 1000 lb and 1-ton models may require wider access. For the 500 lb model, the widest dimension is 12 inches, so doorways are not an issue.",
                None,
            ),
            (
                "What material are your anvils made from?",
                "ACME anvils are forged from high-carbon tool steel with a hardened face (55 HRC). The body is ductile cast steel for shock absorption. This combination gives excellent rebound and durability for years of heavy use.",
                "query_product_database",
            ),
            (
                "Do heavier anvils produce less noise when striking?",
                "Yes, heavier anvils absorb more energy from the hammer blow, resulting in less ringing and vibration. Our 500 lb and 1000 lb models are noticeably quieter. We also sell vibration-dampening pads that reduce noise on any size anvil.",
                None,
            ),
        ],
        "bulk pricing": [
            (
                "I need 50 anvils for our workshop. Do you offer bulk discounts?",
                "Absolutely! For orders of 50 units, we offer a 15% discount off list price. For 100+ units, the discount increases to 20%. I can prepare a custom quote for your workshop order. What size anvils do you need?",
                None,
            ),
            (
                "What's the pricing for {weight} anvils if I order 20?",
                "For an order of 20 {weight} anvils, you'd qualify for our 10% volume discount. I can generate a detailed quote with exact pricing and shipping estimates. Would you like me to send that over?",
                "query_product_database",
            ),
            (
                "We're a school and need anvils for our metalworking program. Any education discounts?",
                "Yes, ACME offers an education program with 25% off for accredited institutions. We also provide a starter kit bundle with 10 anvils, safety equipment, and curriculum guides. I can connect you with our education sales team.",
                None,
            ),
            (
                "Can I set up a recurring order for anvils? We go through about 10 per month.",
                "We offer a subscription program for recurring orders. With a 12-month commitment of 10 units per month, you'd get 18% off plus free shipping. I can set up an account for you with automatic monthly delivery.",
                None,
            ),
            (
                "Do you have a reseller program for anvils?",
                "Yes, our reseller program offers wholesale pricing starting at 25% below retail for qualified businesses. There's a minimum initial order of 25 units. I can send you the reseller application and full pricing tier details.",
                None,
            ),
            (
                "I need a quote for 100 {weight} anvils delivered to {state}.",
                "I'd be happy to prepare that quote. For 100 {weight} anvils delivered to {state}, you qualify for our 20% volume discount plus free freight shipping. I'll have a formal quote ready within 24 hours. Can I get your email?",
                None,
            ),
            (
                "What's your minimum order quantity for bulk pricing?",
                "Bulk pricing starts at 10 units (5% off). At 25 units you get 10%, at 50 units 15%, and at 100+ units 20% off. These discounts apply to any combination of anvil sizes in a single order.",
                None,
            ),
            (
                "Can I mix different anvil sizes in a bulk order and still get the discount?",
                "Yes! Volume discounts are based on total unit count, not per-size. You can mix any combination of sizes in your order. For example, 30 x 100 lb plus 20 x 200 lb would qualify for the 50-unit tier (15% off).",
                None,
            ),
            (
                "We need anvils for all 12 of our locations in {state}. Can you do drop shipping?",
                "Absolutely. We can ship directly to each of your 12 locations in {state}. Multi-location orders still qualify for volume pricing based on total units. We just need a shipping address for each location.",
                None,
            ),
            (
                "Is there a government or military discount on anvils?",
                "Yes, ACME is a GSA-approved vendor. Government and military customers receive preferred pricing (typically 20-30% off retail) and can order through standard procurement channels. I can provide our GSA contract number.",
                None,
            ),
        ],
        "safety": [
            (
                "What safety precautions should I take when using a {weight} anvil?",
                "For a {weight} anvil, always ensure it's mounted on a stable, level surface at knuckle height. Wear safety glasses, hearing protection, and steel-toed boots. Keep a 3-foot clear zone around the anvil during use. Our safety guide covers all the details.",
                "search_knowledge_base",
            ),
            (
                "My anvil fell off the stand. How do I secure it properly?",
                "Anvils should be bolted or chained to a hardwood stump or steel stand rated for the anvil's weight. Never use a wobbly table or unanchored surface. We sell mounting kits designed for each anvil size. Would you like me to recommend one?",
                "search_knowledge_base",
            ),
            (
                "Are ACME anvils OSHA compliant for commercial workshops?",
                "Yes, all ACME anvils meet OSHA standards for commercial metalworking environments when properly installed. We provide compliance documentation and mounting specifications with each anvil. Do you need a copy of the compliance certificate?",
                None,
            ),
            (
                "Can a {weight} anvil be used on the second floor of a building?",
                "A {weight} anvil requires careful floor load assessment. Standard commercial floors typically support 100 lb/sq ft. I'd recommend consulting with your building engineer. We can provide the exact footprint and weight distribution specs.",
                None,
            ),
            (
                "What's the proper way to move a {weight} anvil?",
                "For a {weight} anvil, use a rated hand truck or pallet jack. Never lift anvils over 50 lb without mechanical assistance. For the heavier models, we recommend a forklift or crane. Our delivery team can place the anvil at your workstation for an additional fee.",
                "search_knowledge_base",
            ),
            (
                "Do your anvils come with safety documentation?",
                "Yes, every ACME anvil ships with a safety guide, proper mounting instructions, and recommended PPE list. You can also download the full safety manual from our website. Would you like me to email you a copy?",
                None,
            ),
            (
                "I'm concerned about noise levels in my workshop with multiple anvils.",
                "Multiple anvils can create significant noise. We recommend vibration-dampening pads under each anvil (reduces noise by 40%), and hearing protection rated for 100+ dB. For enclosed workshops, acoustic panels on the walls make a big difference.",
                "search_knowledge_base",
            ),
            (
                "Is there an age requirement for using ACME anvils?",
                "We recommend that users be at least 16 years old, and anyone under 18 should be supervised by a trained adult. Our education program includes age-appropriate safety guidelines for school metalworking programs.",
                None,
            ),
            (
                "My {weight} anvil has sharp edges. Is that normal or a defect?",
                "Some edges on a new anvil are intentionally sharp for specific metalworking techniques. However, if edges are rough, jagged, or have burrs, that may be a manufacturing defect. Could you describe which edges are concerning?",
                None,
            ),
            (
                "What PPE do you recommend for anvil work?",
                "Essential PPE for anvil work includes: safety glasses (ANSI Z87.1 rated), leather gloves, hearing protection (NRR 25+), steel-toed boots, and a leather apron. For heavy forging, add a face shield. We sell PPE bundles designed for anvil work.",
                "search_knowledge_base",
            ),
        ],
    },
    # ── Rocket Skates ───────────────────────────────────────────────────
    "Rocket Skates": {
        "speed settings": [
            (
                "How do I adjust the speed settings on my Rocket Skates?",
                "Rocket Skates have five speed modes: Cruise ({speed_low}), Sport, Turbo, Extreme, and Ludicrous ({speed_high}). Use the dial on the right skate to cycle through modes. Start in Cruise mode until you're comfortable with the handling.",
                "search_knowledge_base",
            ),
            (
                "What's the top speed of the Rocket Skates?",
                "The maximum rated speed is {speed_high} in Ludicrous mode. However, we recommend staying in Sport mode ({speed_low}) for daily use. Extreme and Ludicrous modes are intended for experienced users only and require the safety harness.",
                "query_product_database",
            ),
            (
                "My Rocket Skates are stuck in Cruise mode. I can't change speed.",
                "This usually means the speed limiter is engaged. Check the small switch on the underside of the left skate. If it's in the 'locked' position, flip it to 'unlocked.' If the issue persists, the speed controller may need recalibration.",
                "search_knowledge_base",
            ),
            (
                "Can I set a custom speed limit on my child's Rocket Skates?",
                "Yes, the parental control feature lets you set a maximum speed. Hold the dial button for 5 seconds to enter settings mode, then select 'Speed Limit.' You can cap the top speed at any value from 10 mph to {speed_low}.",
                None,
            ),
            (
                "Is there a way to gradually increase speed instead of jumping between modes?",
                "The latest firmware update (v3.2) added a 'Smooth Ramp' feature that provides gradual acceleration. Connect your skates to the ACME app via Bluetooth and enable it under Settings > Acceleration > Smooth Ramp.",
                "search_knowledge_base",
            ),
            (
                "My left skate accelerates faster than the right one. Is that normal?",
                "No, both skates should accelerate evenly. This could indicate a calibration drift. Try resetting both skates by holding the power button for 10 seconds. If the imbalance persists, the left thruster nozzle may need cleaning.",
                None,
            ),
            (
                "Do Rocket Skates have a speed governor for use in residential areas?",
                "Yes, the Neighborhood Mode limits speed to 15 mph and reduces engine noise by 60%. You can enable it through the ACME app or by triple-clicking the dial. It's required by local ordinances in some areas.",
                None,
            ),
            (
                "What happens if I hit top speed and keep accelerating?",
                "At maximum speed, the skates automatically engage a speed limiter. The thrusters reduce power to maintain a safe maximum. The onboard computer prevents over-acceleration to protect both the user and the engine.",
                None,
            ),
            (
                "How accurate is the speedometer on the Rocket Skates?",
                "The built-in speedometer is accurate to within +/- 2 mph at speeds under 100 mph. At higher speeds, we recommend using the ACME app's GPS-based speed tracking for more precise readings.",
                None,
            ),
            (
                "Can I unlock faster speed modes? My skates only go up to Sport mode.",
                "The basic model ships with Cruise and Sport modes. Turbo, Extreme, and Ludicrous modes require the Pro license upgrade ($49). You can purchase it through the ACME app and it activates immediately.",
                "query_product_database",
            ),
        ],
        "fuel/charging": [
            (
                "How do I charge my Rocket Skates?",
                "Plug the included charging cable into the port on the heel of each skate. A full charge takes about 4 hours and provides approximately 30 miles of range in Cruise mode. The LED indicator turns green when fully charged.",
                "search_knowledge_base",
            ),
            (
                "What type of fuel do the Rocket Skates use?",
                "Current-generation Rocket Skates use a rechargeable lithium-ion power cell (no liquid fuel). Older models (pre-2024) used ACME Rocket Fuel cartridges. Check the model number on the tongue of the skate to confirm which type you have.",
                "query_product_database",
            ),
            (
                "My Rocket Skates won't charge. The LED stays red.",
                "A persistent red LED usually indicates a battery temperature issue. Let the skates cool to room temperature (about 30 minutes) and try again. If the issue persists, the charging port may need cleaning. Use compressed air to clear any debris.",
                None,
            ),
            (
                "How long does a full charge last at top speed?",
                "At maximum speed ({speed_high}), battery life is approximately 8-10 miles. In Sport mode, you'll get about 20 miles, and in Cruise mode ({speed_low}), about 30 miles. Range varies based on terrain and rider weight.",
                None,
            ),
            (
                "Can I use a third-party charger with my Rocket Skates?",
                "We strongly recommend using only the ACME-certified charger. Third-party chargers may not regulate voltage correctly and could damage the battery or void your warranty. Replacement chargers are available for $29 on our website.",
                None,
            ),
            (
                "Is it safe to charge Rocket Skates overnight?",
                "Yes, the built-in charge controller automatically stops charging when the battery is full. It's safe to leave them plugged in overnight. Just make sure they're on a non-flammable surface and away from direct heat.",
                None,
            ),
            (
                "How do I check my battery level?",
                "Press the dial button once to display the battery level on the heel LED. Green means 60-100%, yellow is 20-60%, and red is below 20%. You can also check exact percentages in the ACME app.",
                "search_knowledge_base",
            ),
            (
                "My Rocket Skates only last 10 miles instead of the rated 30. What's wrong?",
                "Reduced range can result from consistently using higher speed modes, cold weather, or an aging battery. After 500 charge cycles, capacity drops to about 80%. Try a full discharge/recharge cycle. If range doesn't improve, the battery may need replacement.",
                None,
            ),
            (
                "Where can I buy replacement batteries for my Rocket Skates?",
                "Replacement batteries are available on our website and through authorized ACME retailers. The standard battery is $89 and the extended-range battery is $129. We also offer a battery subscription for $8/month with annual replacements.",
                "query_product_database",
            ),
            (
                "Do the Rocket Skates support fast charging?",
                "The Pro model supports fast charging: 80% in 45 minutes with the ACME Fast Charger ($49 accessory). The standard model charges at the normal rate regardless of charger type. You can check your model in the ACME app.",
                None,
            ),
        ],
        "safety equipment": [
            (
                "What safety gear do I need for Rocket Skates?",
                "At minimum, you need an ACME-certified helmet, wrist guards, knee pads, and elbow pads. For speeds above {speed_low}, we also require the ACME Safety Harness. All gear is available in our Safety Bundle for $149.",
                "search_knowledge_base",
            ),
            (
                "Do Rocket Skates come with a helmet?",
                "The standard package does not include a helmet. We strongly recommend the ACME RocketHelm ($79) which is specifically rated for high-speed skating. Any DOT or SNELL certified helmet will also work.",
                None,
            ),
            (
                "My kid wants Rocket Skates. What safety features are built in?",
                "Rocket Skates include: automatic speed limiting (parental controls), emergency brake system (squeeze both heels), stability assist for beginners, and an auto-shutoff if the rider falls. We also sell a youth safety kit.",
                "query_product_database",
            ),
            (
                "How does the emergency brake work on the Rocket Skates?",
                "Squeeze both heels together firmly to engage the emergency brake. The skates will decelerate at a controlled rate. At speeds above {speed_low}, braking takes approximately 50 feet. Practice braking at low speeds first.",
                "search_knowledge_base",
            ),
            (
                "Is the safety harness really necessary? It looks uncomfortable.",
                "For speeds above {speed_low}, the safety harness is required by our terms of use and strongly recommended for your protection. The latest V3 harness is much more comfortable with breathable mesh and adjustable straps.",
                None,
            ),
            (
                "Are Rocket Skates street legal? Do I need a license?",
                "Regulations vary by location. In most US states, Rocket Skates are classified as personal mobility devices and are legal on sidewalks and bike lanes. Some cities require registration. Check your local ordinances.",
                None,
            ),
            (
                "The stability assist feature keeps activating. How do I turn it off?",
                "Stability assist can be disabled in the ACME app under Settings > Safety > Stability Assist. Note: disabling it voids the manufacturer's safety recommendation. You must acknowledge the warning in the app to proceed.",
                None,
            ),
            (
                "Can Rocket Skates be used in the rain?",
                "The skates are rated IP54 for water resistance, so light rain is fine. However, we don't recommend use in heavy rain or standing water, as traction is significantly reduced. The rocket exhaust can also create slippery steam.",
                "search_knowledge_base",
            ),
            (
                "What's the weight limit for Rocket Skates?",
                "The standard model supports riders up to 250 lbs. The Heavy Duty model supports up to 350 lbs. Exceeding the weight limit affects braking distance and speed performance, and is not covered by warranty.",
                "query_product_database",
            ),
            (
                "I had a close call at high speed. Do the skates have any crash detection?",
                "Yes, the onboard accelerometer detects sudden impacts. If a crash is detected, the skates automatically shut off thrusters and can send an alert to your emergency contacts via the ACME app (if configured).",
                None,
            ),
        ],
        "returns/exchanges": [
            (
                "I want to return my Rocket Skates. Order {order_id}.",
                "I can help with that. Rocket Skates can be returned within 30 days for a full refund, as long as they're in original condition. Since your order is {order_id}, let me check the purchase date. Can you confirm the skates are unused or lightly used?",
                "lookup_order",
            ),
            (
                "Can I exchange my standard Rocket Skates for the Pro model?",
                "Yes, exchanges are available within 60 days. The Pro model is $150 more, so you'd pay the difference. The Pro includes fast charging, all speed modes unlocked, and the extended-range battery. Would you like to proceed?",
                "query_product_database",
            ),
            (
                "My Rocket Skates don't fit right. Can I exchange for a different size?",
                "Absolutely. Size exchanges are free within 30 days. We'll send the new size and include a prepaid return label for the original pair. What size do you need? Our sizing guide is available at acme.com/sizing.",
                None,
            ),
            (
                "I received the wrong color Rocket Skates. I ordered red but got blue.",
                "I apologize for the mix-up. I'll arrange a free exchange for the correct color right away. You'll receive the red pair within 3-5 business days, and we'll include a return label for the blue pair. No need to send them back first.",
                "lookup_order",
            ),
            (
                "How long does the return process take for Rocket Skates?",
                "Once we receive your returned skates, refunds are processed within 5-7 business days. The return shipping label is prepaid, and ground shipping back to us takes 3-5 days. So total time from shipping to refund is about 10-12 days.",
                None,
            ),
            (
                "Can I return Rocket Skates I bought on sale?",
                "Sale items can be returned within 14 days (instead of the standard 30) for a refund at the sale price. Exchanges are still available within 60 days. What's your order number so I can look into this?",
                None,
            ),
            (
                "I've had my Rocket Skates for 45 days. Is it too late to return them?",
                "Unfortunately, our return window is 30 days. However, I can offer you a store credit or help with an exchange, which has a 60-day window. Would either of those options work for you?",
                None,
            ),
            (
                "The Rocket Skates I received seem used. They have scuff marks.",
                "That's unacceptable. I sincerely apologize. I'll send a new, sealed pair immediately and include a return label for the scuffed ones. I'll also flag this with our warehouse team. Can you share your order number?",
                "lookup_order",
            ),
            (
                "I want a refund, not a replacement, for my defective Rocket Skates. Order {order_id}.",
                "I understand. For defective products, we offer both full refund and replacement options. Since you prefer a refund, I'll process that for order {order_id} right away. You'll see it within 5-7 business days after we receive the return.",
                "lookup_order",
            ),
            (
                "Do I need the original box to return Rocket Skates?",
                "The original packaging is preferred but not required. Just make sure the skates are protected during shipping. We'll provide a prepaid return label. Use any sturdy box that fits both skates.",
                None,
            ),
        ],
    },
    # ── Giant Magnets ───────────────────────────────────────────────────
    "Giant Magnets": {
        "strength ratings": [
            (
                "What strength ratings are available for ACME Giant Magnets?",
                "ACME Giant Magnets come in five strength ratings: 500, 1000, 2500, 5000, and 10000 gauss. The 1000 gauss model is our most popular for general use. Higher ratings are typically used for industrial and scientific applications.",
                "query_product_database",
            ),
            (
                "What's the pull force of the {magnet_strength} Giant Magnet?",
                "The {magnet_strength} model has a pull force of approximately {magnet_strength} at surface contact, decreasing with distance. At 1 inch, the effective pull is roughly 60% of rated strength. I can send you the full distance-strength chart.",
                "query_product_database",
            ),
            (
                "Which Giant Magnet is strong enough to lift a car?",
                "To lift a standard 3,500 lb vehicle, you'd need our 10000 gauss industrial model. It has a rated pull force of over 5,000 lbs at contact. Please note that vehicle lifting requires proper rigging and is for professional use only.",
                "query_product_database",
            ),
            (
                "Can I use the {magnet_strength} magnet for metal separation in recycling?",
                "The {magnet_strength} model works well for ferrous metal separation. For mixed-metal recycling, we recommend at least 2500 gauss. The magnet should be suspended above the conveyor at a height calculated from the strength rating tables.",
                None,
            ),
            (
                "Do the magnets lose strength over time?",
                "ACME Giant Magnets are made from neodymium alloy and maintain over 95% of their rated strength for 100+ years under normal conditions. Excessive heat (above 175F) can cause permanent demagnetization. Store below 150F for best results.",
                "search_knowledge_base",
            ),
            (
                "What's the difference between the 2500 and 5000 gauss models?",
                "The 5000 gauss model is physically larger (18 inches vs 12 inches diameter) and has roughly double the pull force and effective range. The 2500 is more portable and suitable for workshop use, while the 5000 is better for heavy industrial applications.",
                "query_product_database",
            ),
            (
                "I need a magnet for a science fair project. What do you recommend?",
                "For science projects, our 500 gauss model is ideal. It's powerful enough for impressive demonstrations but manageable in size and weight. It comes with a carrying case and safety documentation suitable for educational settings.",
                None,
            ),
            (
                "Are your magnets rated for underwater use?",
                "Our standard Giant Magnets are rated for temporary submersion (IP67). For prolonged underwater use, such as magnet fishing or marine salvage, we offer a marine-coated version with full corrosion resistance. Which application did you have in mind?",
                "query_product_database",
            ),
            (
                "How do I measure the actual strength of my Giant Magnet?",
                "You can use a gaussmeter to measure the surface field strength. We sell the ACME GaussMaster ($39) which connects to our app and provides accurate readings. If your magnet measures below 90% of its rating, it may need replacement.",
                None,
            ),
            (
                "Can two Giant Magnets be combined for more pull force?",
                "Yes, stacking magnets in the same polarity orientation increases pull force, though it's not perfectly additive (two 1000 gauss magnets yield about 1700 effective gauss). Be extremely careful when handling multiple large magnets near each other.",
                "search_knowledge_base",
            ),
        ],
        "electronic interference": [
            (
                "Will the Giant Magnet damage my phone or laptop?",
                "Yes, keep all electronics at least 3 feet from the {magnet_strength} model. Strong magnets can damage hard drives, erase credit cards, and interfere with phone sensors. We recommend a 5-foot buffer for magnets above 2500 gauss.",
                "search_knowledge_base",
            ),
            (
                "My credit cards got wiped after using a Giant Magnet. What happened?",
                "The magnetic strip on credit cards is vulnerable to strong magnetic fields. This is unfortunately permanent. I recommend using chip or contactless payments near magnets. Store all cards and electronics outside the work area.",
                None,
            ),
            (
                "What's the safe distance for electronics around a {magnet_strength} magnet?",
                "For the {magnet_strength} model, keep electronics at least 5 feet away. Pacemakers and other medical devices require a minimum of 10 feet. We include a magnetic field boundary chart with every Giant Magnet purchase.",
                "search_knowledge_base",
            ),
            (
                "Can the Giant Magnet interfere with my Wi-Fi or Bluetooth?",
                "Static magnetic fields from our magnets don't directly interfere with Wi-Fi or Bluetooth radio signals. However, if the magnet is near the router or device antenna, the metal components can be affected. A 3-foot distance should prevent any issues.",
                None,
            ),
            (
                "I have a pacemaker. Can I use a Giant Magnet safely?",
                "We strongly advise against using Giant Magnets if you have a pacemaker or any implanted medical device. Even our weakest model (500 gauss) can affect pacemaker function within several feet. Please consult your doctor before considering use.",
                "search_knowledge_base",
            ),
            (
                "Will a Giant Magnet erase a USB flash drive?",
                "USB flash drives use solid-state memory (not magnetic storage) and are generally not affected by magnetic fields. However, the drive's metal casing could be pulled toward the magnet forcefully, potentially causing physical damage.",
                None,
            ),
            (
                "My compass doesn't work anymore after being near the Giant Magnet.",
                "A strong magnetic field can temporarily or permanently re-magnetize a compass needle. Try degaussing the compass by slowly rotating it near a weak alternating magnetic field. If that doesn't work, the compass needle may need replacement.",
                None,
            ),
            (
                "Can I use the Giant Magnet near my CNC machine?",
                "Use caution. The magnet can attract metal chips and tools toward it, and strong fields can interfere with some CNC stepper motors and encoders. We recommend at least 6 feet of clearance from sensitive machinery.",
                "search_knowledge_base",
            ),
            (
                "How do I shield electronics from the Giant Magnet's field?",
                "Mu-metal shielding is the most effective solution. We sell ACME MagShield panels ($29 each) that reduce the field by 90%. For critical electronics, an enclosed mu-metal box provides nearly complete protection.",
                "query_product_database",
            ),
            (
                "Will the Giant Magnet affect my mechanical watch?",
                "Yes, strong magnetic fields can magnetize the hairspring in mechanical watches, causing them to run fast. Keep watches at least 3 feet away. If your watch has been affected, a watchmaker can degauss it for about $20.",
                None,
            ),
        ],
        "mounting/installation": [
            (
                "How do I mount a {magnet_strength} Giant Magnet?",
                "The {magnet_strength} model includes a mounting bracket rated for its pull force. Secure the bracket to a steel structure using the provided grade-8 bolts. For overhead mounting, you must use the safety chain as a backup. The manual covers installation step by step.",
                "search_knowledge_base",
            ),
            (
                "Can I mount the Giant Magnet on a ceiling?",
                "Ceiling mounting is supported for all models up to 5000 gauss with the ACME Overhead Mounting Kit ($89). The ceiling structure must support at least 3x the magnet's weight plus the rated pull force. A safety chain is mandatory.",
                "query_product_database",
            ),
            (
                "What surface do I need to mount the Giant Magnet on?",
                "The magnet needs a ferrous (iron/steel) mounting surface for maximum hold, or you can use the included mounting bracket on any structural surface (concrete, steel beam, heavy timber) with appropriate fasteners.",
                None,
            ),
            (
                "I need to install a Giant Magnet on a conveyor system. Do you offer professional installation?",
                "Yes, ACME offers professional installation through our certified technician network. For conveyor systems, this is strongly recommended. Installation includes alignment, safety testing, and a compliance certificate. Costs start at $299.",
                None,
            ),
            (
                "How do I safely remove a Giant Magnet once it's attached to a surface?",
                "Never try to pull a Giant Magnet straight off a surface. Use the included sliding technique: push the magnet laterally to the edge of the surface. For larger models, use the ACME MagRelease lever ($49) which provides mechanical advantage.",
                "search_knowledge_base",
            ),
            (
                "Can I mount two Giant Magnets facing each other?",
                "This is extremely dangerous and not recommended. Opposing magnets create a very strong attractive force that can cause serious injury if hands or body parts are caught between them. If you need this configuration, contact our engineering team for a custom solution.",
                None,
            ),
            (
                "My Giant Magnet won't hold to the mounting surface. What's wrong?",
                "Check that the surface is ferrous metal (stainless steel is often non-magnetic). Also ensure the surface is clean, flat, and free of paint or coatings thicker than 1mm. An air gap of even 1mm reduces holding force by 20-30%.",
                "search_knowledge_base",
            ),
            (
                "Is there a vibration-dampening mount for the Giant Magnet?",
                "Yes, our ACME VibMount ($69) absorbs vibration and is recommended for magnets used in industrial environments with heavy machinery. It also reduces the noise from magnetic cycling.",
                "query_product_database",
            ),
            (
                "Do I need a permit to install a Giant Magnet at my business?",
                "Requirements vary by jurisdiction. Industrial magnets above 5000 gauss may require a safety inspection. We recommend checking with your local building authority. Our installation team can handle the permitting process if needed.",
                None,
            ),
            (
                "What tools do I need to install the Giant Magnet?",
                "You'll need: a socket wrench set (metric), a level, a drill with masonry/steel bits (depending on surface), and the included mounting hardware. For models above 2500 gauss, a hoist or lift is recommended for positioning.",
                None,
            ),
        ],
    },
    # ── Portable Holes ──────────────────────────────────────────────────
    "Portable Holes": {
        "placement/usage": [
            (
                "How do I use a Portable Hole?",
                "Simply unroll the Portable Hole and place it on any flat surface. It adheres automatically and creates an instant opening. To remove it, peel from one edge and roll it back up. Always check the other side before stepping through.",
                "search_knowledge_base",
            ),
            (
                "Can I place a Portable Hole on a vertical surface like a wall?",
                "Yes, Portable Holes work on walls, floors, and ceilings. On vertical surfaces, the adhesive is strong enough to hold. Just make sure the surface is clean and dry. Note that the hole creates a passage through the full thickness of the wall.",
                None,
            ),
            (
                "My Portable Hole won't stick to the surface. What's going on?",
                "Portable Holes require a clean, dry, non-porous surface. If the surface is dusty, wet, or coated in oil, the hole won't adhere. Clean the surface with rubbing alcohol and try again. Extremely cold surfaces (below 32F) can also prevent adhesion.",
                "search_knowledge_base",
            ),
            (
                "Can I use a Portable Hole on glass?",
                "Portable Holes work on glass, but use caution: the hole removes a section of the glass surface. When the hole is removed, the glass is restored. However, very thin glass may crack from the stress. We recommend glass at least 1/4 inch thick.",
                None,
            ),
            (
                "What happens if I place two Portable Holes on top of each other?",
                "Stacking Portable Holes is not recommended and can create unpredictable spatial distortions. Our engineers strongly advise against this. Each Portable Hole should be used independently with at least 10 feet between placements.",
                "search_knowledge_base",
            ),
            (
                "Can the Portable Hole be used outdoors?",
                "Yes, Portable Holes work outdoors on solid surfaces (concrete, asphalt, rock). They don't work on loose materials like dirt, sand, or gravel. Wind above 40 mph can affect the hole's stability on vertical surfaces.",
                None,
            ),
            (
                "How long can I leave a Portable Hole in place?",
                "Portable Holes can remain in place indefinitely. However, we recommend removing and re-rolling them every 30 days to maintain elasticity. Leaving a hole in place for over 90 days may cause surface staining.",
                None,
            ),
            (
                "Can I walk through a Portable Hole?",
                "Yes, that's one of the primary uses. When placed on a wall or floor, you can step or walk through. Always verify the destination is safe before entering. The hole creates a passage equal to its diameter, so make sure it's large enough.",
                "search_knowledge_base",
            ),
            (
                "I accidentally placed my Portable Hole on the wrong surface. How do I move it?",
                "Simply peel the hole from one edge, starting slowly. It will roll back up without any residue. Then place it on the correct surface. Moving a hole does not affect its performance or adhesion on the new surface.",
                None,
            ),
            (
                "Can items be stored inside a Portable Hole?",
                "Yes, Portable Holes have an internal volume of approximately 10 cubic feet (for the standard {hole_size} model). It's a great way to store or transport items. Just don't exceed the weight capacity of 500 lbs.",
                "query_product_database",
            ),
        ],
        "sizing": [
            (
                "What sizes do Portable Holes come in?",
                "ACME Portable Holes are available in 3 ft, 5 ft, 8 ft, 10 ft, and 12 ft diameters. The 5 ft model is our most popular for personal use, while the 8 ft and 10 ft models are common for commercial applications.",
                "query_product_database",
            ),
            (
                "Which size Portable Hole do I need for a doorway?",
                "A standard doorway is about 3 x 7 feet, so a 5 ft Portable Hole would create a round opening large enough for most people to walk through comfortably. For moving furniture, we recommend the 8 ft model.",
                None,
            ),
            (
                "Can I cut a Portable Hole to make it smaller?",
                "No, cutting a Portable Hole disrupts the spatial matrix and will render it non-functional (and potentially dangerous). If you need a smaller size, please purchase the correct diameter. We offer exchanges within 30 days.",
                None,
            ),
            (
                "Is the {hole_size} model big enough for a vehicle?",
                "The {hole_size} model can accommodate most compact cars. For full-size vehicles, we recommend the 10 ft or 12 ft models. Measure your vehicle's widest point and add 1 foot of clearance on each side.",
                "query_product_database",
            ),
            (
                "What's the depth of a Portable Hole?",
                "Portable Holes pass through the surface they're placed on, so the 'depth' equals the thickness of that surface. On a 6-inch wall, it's 6 inches deep. The internal storage volume is a fixed 10 cubic feet regardless of placement.",
                None,
            ),
            (
                "Do larger Portable Holes weigh more?",
                "Yes, slightly. The 3 ft model weighs 2 lbs, the 5 ft is 3 lbs, the 8 ft is 5 lbs, the 10 ft is 7 lbs, and the 12 ft is 9 lbs. All models roll up to roughly the same diameter (about 4 inches), varying only in length.",
                "query_product_database",
            ),
            (
                "I need a Portable Hole for industrial piping. Do you make custom sizes?",
                "Yes, custom-diameter Portable Holes are available for industrial applications. We can manufacture any diameter from 1 ft to 20 ft. Custom orders take 2-3 weeks and require a consultation with our engineering team.",
                None,
            ),
            (
                "Can I stretch a Portable Hole to make it larger?",
                "No, stretching a Portable Hole beyond its rated diameter will compromise the spatial integrity. The material is designed to maintain a precise diameter. Overstretching can cause tears, which are irreparable.",
                None,
            ),
            (
                "What's the rolled-up size of the {hole_size} Portable Hole?",
                "The {hole_size} Portable Hole rolls up to approximately 4 inches in diameter and {hole_size} in length (equal to the diameter). It comes with a carrying tube for easy transport.",
                None,
            ),
            (
                "Do you have a sample pack with multiple sizes?",
                "We offer the ACME Portable Hole Sample Pack which includes 3 ft and 5 ft models at a 20% bundle discount. It's a great way to test different sizes before committing to a larger model for your project.",
                "query_product_database",
            ),
        ],
        "safety": [
            (
                "Are Portable Holes safe to use?",
                "Yes, when used according to the instructions. Key safety rules: always check the destination before entering, never stack holes, keep away from children under 12, and don't use on surfaces that may collapse. Our safety guide covers all precautions.",
                "search_knowledge_base",
            ),
            (
                "Can I fall through a Portable Hole on the floor?",
                "If placed on a floor, the hole creates an opening to whatever is below. On the ground floor, this would be soil or foundation. On upper floors, you could fall to the floor below. Always secure floor-mounted holes with the included safety rail kit.",
                "search_knowledge_base",
            ),
            (
                "Is there a way to lock a Portable Hole so no one can enter?",
                "Yes, the ACME HoleLock accessory ($39) attaches to the edge of the hole and prevents entry. It works like a manhole cover but is integrated with the hole's edge. You can also set a combination code for authorized access.",
                "query_product_database",
            ),
            (
                "My cat fell into a Portable Hole. How do I get it out?",
                "Don't panic. If the hole is on a floor, your cat is in the internal storage space (10 cubic feet). Simply tip the hole to a 45-degree angle, and the cat should be able to climb out. If the hole passes through a wall, check the other side.",
                None,
            ),
            (
                "What happens if a Portable Hole gets damaged or torn?",
                "A torn Portable Hole loses spatial coherence and should not be used. Seal it in the included containment bag and contact ACME for a replacement. Do not attempt to repair it yourself. Damaged holes are covered under warranty.",
                None,
            ),
            (
                "Can a Portable Hole be used as a fire escape?",
                "While technically possible, Portable Holes are not certified as fire safety equipment. In an emergency, the time needed to position the hole may be better spent using standard exits. Check with your local fire marshal for building code compliance.",
                None,
            ),
            (
                "Is there a risk of suffocation inside a Portable Hole's storage space?",
                "The internal storage space has limited air volume. Do not allow people or animals to remain inside for more than 15 minutes. For extended use, the ACME HoleVent accessory ($19) provides passive air circulation.",
                "search_knowledge_base",
            ),
            (
                "Are Portable Holes legal to carry in public?",
                "In most jurisdictions, Portable Holes are treated as tools and are legal to carry. However, some cities have restrictions on deploying them in public spaces. Rolled up and in a carrying tube, they're universally permitted.",
                None,
            ),
            (
                "What age is appropriate for using a Portable Hole?",
                "We recommend ages 16 and up for unsupervised use, and ages 12-15 with adult supervision. Children under 12 should not handle Portable Holes. The adhesive and spatial properties require responsible use.",
                None,
            ),
            (
                "Can a Portable Hole be used on an airplane?",
                "Portable Holes are prohibited on commercial aircraft as carry-on or checked luggage. The FAA classifies them as restricted spatial devices. They can be shipped as freight with proper ACME Spatial Hazard packaging.",
                None,
            ),
        ],
        "storage/maintenance": [
            (
                "How do I store my Portable Hole when not in use?",
                "Roll the hole tightly from one edge, place it in the included carrying tube, and store in a cool, dry location. Avoid folding (only roll). Keep away from direct sunlight and temperatures above 120F.",
                "search_knowledge_base",
            ),
            (
                "My Portable Hole has wrinkles. Does that affect performance?",
                "Minor wrinkles from storage are normal and don't affect performance. They'll smooth out once placed on a surface. Deep creases, however, can create spatial distortions. If you see deep creases, try laying the hole flat for 24 hours.",
                None,
            ),
            (
                "How do I clean a Portable Hole?",
                "Wipe both sides with a damp cloth and mild soap. Do not submerge the hole in water while it's rolled up, as trapped moisture can cause mildew. Allow it to dry fully before rolling and storing.",
                None,
            ),
            (
                "What's the lifespan of a Portable Hole?",
                "With proper care, an ACME Portable Hole lasts 10-15 years. Signs of aging include reduced adhesion, slight discoloration, and slower spatial activation. We recommend replacing the hole if adhesion drops noticeably.",
                "query_product_database",
            ),
            (
                "Can I leave items stored inside a Portable Hole while it's rolled up?",
                "Yes, items remain in the internal storage space when the hole is rolled. The maximum storage weight is 500 lbs. Heavy items stored while rolled can make the hole difficult to deploy, so remove heavy items before unrolling.",
                None,
            ),
            (
                "My Portable Hole is losing adhesion. Is there a way to restore it?",
                "Try cleaning both the hole and the mounting surface with rubbing alcohol. If adhesion is still weak, apply the ACME HoleGrip adhesive booster ($15), which restores sticking power. If the hole is over 10 years old, it may be time for a replacement.",
                "query_product_database",
            ),
            (
                "Does temperature affect Portable Hole performance?",
                "Optimal performance is between 40F and 100F. Below 32F, adhesion weakens and the material stiffens. Above 120F, the spatial matrix can destabilize. Always store at room temperature.",
                None,
            ),
            (
                "Can I fold a Portable Hole instead of rolling it?",
                "No, never fold a Portable Hole. Folding creates sharp creases that damage the spatial matrix and can cause unpredictable behavior. Always roll from one edge. The carrying tube is designed to prevent accidental folding.",
                "search_knowledge_base",
            ),
            (
                "How do I repair a small nick on the edge of my Portable Hole?",
                "Small edge nicks can be sealed with the included ACME SpatialSeal tape. Apply a 1-inch piece over the nick and smooth firmly. Larger tears (over 1 inch) cannot be repaired safely. Contact us for a warranty replacement.",
                None,
            ),
            (
                "Is there a maintenance schedule for Portable Holes?",
                "We recommend: monthly inspections (check edges for nicks), quarterly cleaning, and annual adhesion testing. If used daily, inspect weekly. The ACME app can set maintenance reminders based on your usage pattern.",
                None,
            ),
        ],
    },
    # ── Earthquake Pills ────────────────────────────────────────────────
    "Earthquake Pills": {
        "dosage/ratings": [
            (
                "What Richter scale ratings are available for Earthquake Pills?",
                "ACME Earthquake Pills come in {quake_rating}-rated models plus custom strengths. The most common are 3.0 (light), 4.5 (moderate), and 5.0 (strong). Ratings above 6.5 require a commercial license. Which rating interests you?",
                "query_product_database",
            ),
            (
                "How many pills do I need for a {quake_rating} magnitude effect?",
                "One pill produces the rated effect within a 100-yard radius for 30 seconds. For larger areas, use additional pills spaced 150 yards apart. Never exceed 3 pills simultaneously in the same area, as effects can compound unpredictably.",
                "search_knowledge_base",
            ),
            (
                "Can I take half a pill for a smaller earthquake effect?",
                "No, pills must be used whole. Splitting a pill creates an uneven chemical distribution that can result in uncontrolled vibration patterns. If you need a lower magnitude, purchase the appropriate lower-rated pill.",
                None,
            ),
            (
                "What's the difference between a 3.0 and a 5.0 pill?",
                "A 3.0 pill produces noticeable shaking similar to a truck passing (items rattle, no damage). A 5.0 pill causes significant ground movement that can topple unsecured objects and crack unreinforced structures. Choose based on your application.",
                "query_product_database",
            ),
            (
                "How long does the earthquake effect last?",
                "Standard pills produce a 30-second event. Extended-duration pills (60 and 120 seconds) are available for professional applications. The effect begins 10 seconds after activation, giving you time to reach a safe observation distance.",
                None,
            ),
            (
                "Is there a maximum number of pills I can purchase?",
                "Consumer purchases are limited to 12 pills per month (max 4.5 rating). Commercial license holders can purchase up to 100 pills per month at higher ratings. This is for safety compliance and regulatory tracking.",
                None,
            ),
            (
                "Do the pills work on all types of ground?",
                "Pills are calibrated for standard soil and rock. Sandy or loose soil amplifies the effect by about 20%, while solid bedrock dampens it by about 15%. The packaging includes a soil-type adjustment chart.",
                "search_knowledge_base",
            ),
            (
                "Can weather affect the pill's performance?",
                "Heavy rain and saturated soil can amplify the effect by 10-30%. Frozen ground reduces effectiveness by about 25%. For the most predictable results, use in dry conditions at temperatures between 40F and 90F.",
                None,
            ),
            (
                "I need a precise {quake_rating} magnitude. How accurate are the pills?",
                "Pills are accurate to +/- 0.3 on the Richter scale under standard soil conditions. For precision applications, we offer lab-calibrated pills (accurate to +/- 0.1) at a premium. Would you like details on the calibrated series?",
                "query_product_database",
            ),
            (
                "Are there Earthquake Pills for controlled demolition?",
                "Yes, our Professional Demolition Series is designed for structural demolition. These pills (rated 6.5-8.0) are only available to licensed demolition contractors and require pre-approval from ACME's safety division.",
                None,
            ),
        ],
        "licensing/compliance": [
            (
                "Do I need a license to purchase Earthquake Pills?",
                "Consumer-grade pills (up to 4.5 magnitude) can be purchased without a license by adults 21 and over. Pills rated 5.0 and above require an ACME Commercial Seismic License, which involves a safety course and background check.",
                "search_knowledge_base",
            ),
            (
                "How do I get a commercial license for higher-rated pills?",
                "The ACME Commercial Seismic License requires: (1) completion of our 8-hour safety course, (2) passing the written and practical exams, (3) a background check, and (4) proof of liability insurance. The process takes about 2-3 weeks.",
                None,
            ),
            (
                "Are Earthquake Pills legal in {state}?",
                "Earthquake Pills are regulated at the state level. Most states allow consumer-grade pills (4.5 and below). However, {state} may have specific restrictions. I can look up the current regulations for {state} if you'd like.",
                "search_knowledge_base",
            ),
            (
                "What permits do I need to use Earthquake Pills commercially?",
                "Commercial use requires: an ACME Seismic License, a local blasting/vibration permit, notification to the USGS 48 hours before use, and liability insurance. Our compliance team can help you navigate the permitting process.",
                None,
            ),
            (
                "Can I use Earthquake Pills in a residential area?",
                "Consumer-grade pills (3.0) can be used in residential areas with proper notification to neighbors (24-hour advance notice required). Pills rated 4.0 and above require a 500-yard clearance from occupied structures. Check local ordinances first.",
                "search_knowledge_base",
            ),
            (
                "My license is expiring soon. How do I renew it?",
                "Commercial Seismic Licenses renew annually. You'll need to complete a 4-hour refresher course and submit proof of current liability insurance. Renewals can be done online through the ACME portal. Start the process at least 30 days before expiration.",
                None,
            ),
            (
                "Are there age restrictions for purchasing Earthquake Pills?",
                "Yes, you must be at least 21 years old to purchase any Earthquake Pills. Photo ID is required at the time of purchase. For educational use with minors, a licensed instructor must be present and responsible for handling.",
                None,
            ),
            (
                "What happens if I use Earthquake Pills without proper permits?",
                "Unauthorized use of Earthquake Pills can result in fines up to $50,000, criminal charges, and a permanent ban from purchasing ACME seismic products. We take compliance seriously and report violations to relevant authorities.",
                None,
            ),
            (
                "Can I export Earthquake Pills to another country?",
                "International export requires an ACME Export License and compliance with the destination country's seismic device regulations. Many countries prohibit importation entirely. Contact our international sales team for guidance.",
                None,
            ),
            (
                "Do I need to register each pill I purchase?",
                "Yes, every Earthquake Pill has a unique serial number that's registered to the buyer at point of sale. Commercial license holders must also log each use, including date, location, and magnitude. Records are auditable by ACME and regulators.",
                None,
            ),
        ],
        "shelf life": [
            (
                "What's the shelf life of Earthquake Pills?",
                "ACME Earthquake Pills have a 5-year shelf life when stored properly. The expiration date is printed on each pill's blister pack. After expiration, effectiveness may decrease and behavior can become unpredictable. Do not use expired pills.",
                "query_product_database",
            ),
            (
                "How should I store Earthquake Pills?",
                "Store in a cool, dry place between 50F and 80F. Keep pills in the original blister packaging until use. Avoid humidity above 60%, direct sunlight, and proximity to heat sources. A locked cabinet is recommended for both safety and compliance.",
                "search_knowledge_base",
            ),
            (
                "My Earthquake Pills expired last month. Are they still safe to use?",
                "We do not recommend using expired pills. The chemical compounds degrade over time, which can cause inconsistent magnitude, unpredictable duration, or failure to activate. Return expired pills to ACME for safe disposal at no charge.",
                None,
            ),
            (
                "Can I extend the shelf life by refrigerating the pills?",
                "Refrigeration (not freezing) can extend shelf life by approximately 1 year. Keep pills above 40F, as freezing damages the chemical matrix. This unofficial extension isn't guaranteed, so use refrigerated expired pills at your own risk.",
                None,
            ),
            (
                "How do I dispose of expired Earthquake Pills?",
                "Never throw Earthquake Pills in regular trash. Return them to any ACME retail location or mail them using the prepaid ACME Disposal Kit. We safely neutralize the seismic compounds at our facilities. Disposal is free of charge.",
                "search_knowledge_base",
            ),
            (
                "Do the pills degrade if shipped in hot weather?",
                "Brief exposure to heat during shipping (up to 120F for 48 hours) is fine. Our packaging includes thermal insulation. However, if the heat indicator strip on the package has turned red, the pills may be compromised. Contact us for a replacement.",
                None,
            ),
            (
                "I found Earthquake Pills in my garage that are 3 years old. Are they OK?",
                "If they've been stored below 80F and the blister packs are intact and not discolored, they should be fine. Check the expiration date on each pack. If storage conditions were uncertain (hot garage in summer), I'd recommend replacing them.",
                None,
            ),
            (
                "Can humidity affect the pills during storage?",
                "Yes, humidity above 60% can cause the outer coating to soften, which affects activation timing. Store pills in low-humidity environments. If the blister pack feels soft or the pill appears swollen, do not use it.",
                None,
            ),
            (
                "What are the signs that an Earthquake Pill has gone bad?",
                "Warning signs include: discoloration (pills should be uniform gray), crumbling or powdery texture, unusual odor, swollen blister pack, or the heat indicator turning red. Any of these mean the pill should be disposed of through ACME's program.",
                None,
            ),
            (
                "Is there a bulk storage container for Earthquake Pills?",
                "Yes, the ACME SeismoVault ($129) is a climate-controlled storage unit that holds up to 50 pills. It maintains optimal temperature and humidity, and includes a tamper-proof lock for compliance. It also logs storage conditions for auditing.",
                "query_product_database",
            ),
        ],
        "disposal": [
            (
                "How do I dispose of Earthquake Pills I no longer need?",
                "Return unused pills to any ACME retail location or use our prepaid disposal mailer. Never throw them in regular trash, flush them, or bury them. Our disposal team safely neutralizes the seismic compounds.",
                "search_knowledge_base",
            ),
            (
                "Is there a fee for Earthquake Pill disposal?",
                "No, ACME provides free disposal for all our seismic products. We include a prepaid disposal mailer with orders of 10+ pills. You can also drop them off at any ACME store or authorized collection point.",
                None,
            ),
            (
                "What happens if Earthquake Pills are thrown in the trash?",
                "Improperly disposed pills can activate when crushed in garbage compactors, potentially causing localized seismic events at landfills. This has happened before and resulted in significant fines for the responsible party. Always use proper disposal channels.",
                None,
            ),
            (
                "Can I neutralize Earthquake Pills at home?",
                "No, home neutralization is not safe or effective. The seismic compounds require controlled chemical processing at temperatures exceeding 1000F. Only ACME's certified disposal facilities have the proper equipment. Please use our free disposal service.",
                None,
            ),
            (
                "Where is the nearest Earthquake Pill collection point in {state}?",
                "I can look up ACME collection points in {state}. We have locations in most major cities. You can also check acme.com/disposal for an interactive map. If there's no nearby location, use the prepaid mailer option.",
                "search_knowledge_base",
            ),
            (
                "I'm a business closing down. I have 50+ pills to dispose of. What do I do?",
                "For commercial quantities, schedule a pickup through ACME's Bulk Disposal Service. A certified technician will collect and transport the pills to our disposal facility. Call our commercial line or submit a request at acme.com/commercial-disposal.",
                None,
            ),
            (
                "Can I return unused Earthquake Pills for a refund?",
                "Unopened pills in original packaging can be returned within 90 days for a full refund. After 90 days, we offer free disposal but no refund. The extended return window (vs 30 days for other products) reflects the regulated nature of these items.",
                "lookup_order",
            ),
            (
                "Are there environmental concerns with Earthquake Pill disposal?",
                "When properly disposed through ACME's program, there is zero environmental impact. The neutralization process converts the seismic compounds into inert calcium silicate (basically concrete powder). Improper disposal, however, poses real environmental risks.",
                None,
            ),
            (
                "My Earthquake Pill got wet. Is it still safe?",
                "If the blister pack was sealed and the pill is dry inside, it's fine. If the pill got directly wet, do not use it. Wet pills can have unpredictable activation triggers. Place it in the disposal mailer and request a replacement.",
                None,
            ),
            (
                "How long does the disposal process take after I send pills back?",
                "Once received at our facility, pills are processed within 72 hours. You'll receive a disposal certificate by email confirming safe neutralization. For commercial license holders, this certificate is important for your compliance records.",
                None,
            ),
        ],
    },
}

# ---------------------------------------------------------------------------
# Helper: LLM message formats
# ---------------------------------------------------------------------------
MODEL_NAME = "gpt-4o-mini"


def _llm_input_messages(question: str) -> dict:
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful customer support agent for ACME Industries. "
                    "Answer questions about our products: Anvils, Rocket Skates, "
                    "Giant Magnets, Portable Holes, and Earthquake Pills."
                ),
            },
            {"role": "user", "content": question},
        ]
    }


def _llm_output_messages(response: str, tool_calls: list[dict] | None = None) -> dict:
    msg: dict = {"role": "assistant", "content": response}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "choices": [
            {
                "index": 0,
                "message": msg,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ]
    }


def _tool_call_obj(tool_name: str, arguments: dict) -> dict:
    return {
        "id": f"call_{uuid.uuid4().hex[:24]}",
        "type": "function",
        "function": {"name": tool_name, "arguments": json.dumps(arguments)},
    }


TOOL_ARGS: dict[str, callable] = {
    "lookup_order": lambda: {"order_id": _order_id()},
    "query_product_database": lambda: {"query": "product specifications"},
    "search_knowledge_base": lambda: {"query": "usage guidelines"},
}

TOOL_OUTPUTS: dict[str, callable] = {
    "lookup_order": lambda args: {
        "output": json.dumps(
            {
                "order_id": args.get("order_id", _order_id()),
                "status": random.choice(["shipped", "processing", "delivered", "in_transit"]),
                "estimated_delivery": (
                    datetime.now(timezone.utc) + timedelta(days=random.randint(1, 7))
                ).isoformat(),
            }
        )
    },
    "query_product_database": lambda args: {
        "output": json.dumps(
            {
                "results_count": random.randint(1, 5),
                "source": "acme_product_catalog",
            }
        )
    },
    "search_knowledge_base": lambda args: {
        "output": json.dumps(
            {
                "results_count": random.randint(1, 8),
                "source": "acme_knowledge_base",
            }
        )
    },
}


# ---------------------------------------------------------------------------
# Trace builder
# ---------------------------------------------------------------------------
def build_trace(
    product: str,
    subtopic: str,
    question: str,
    response: str,
    tool_name: str | None,
    base_time: datetime,
) -> list[dict]:
    """Return a list of run dicts (root + LLM + optional tool) for one trace."""
    trace_id = str(uuid.uuid4())
    root_id = str(uuid.uuid4())
    llm_id = str(uuid.uuid4())

    # Timing
    root_start = base_time
    llm_start = root_start + timedelta(milliseconds=random.randint(5, 30))
    runs: list[dict] = []

    tags = [product, subtopic]

    # Decide if we include tool runs
    include_tool = tool_name is not None and random.random() < 0.6

    if include_tool:
        # LLM makes a tool call first
        tool_id = str(uuid.uuid4())
        tool_args = TOOL_ARGS[tool_name]()
        tc_obj = _tool_call_obj(tool_name, tool_args)

        llm_end_1 = llm_start + timedelta(milliseconds=random.randint(300, 800))
        tool_start = llm_end_1 + timedelta(milliseconds=random.randint(5, 20))
        tool_end = tool_start + timedelta(milliseconds=random.randint(50, 300))

        # Second LLM call after tool result
        llm2_id = str(uuid.uuid4())
        llm2_start = tool_end + timedelta(milliseconds=random.randint(5, 20))
        llm2_end = llm2_start + timedelta(milliseconds=random.randint(400, 1200))
        root_end = llm2_end + timedelta(milliseconds=random.randint(5, 30))

        # LLM run 1 (tool-calling)
        runs.append(
            {
                "id": llm_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": "ChatOpenAI",
                "run_type": "llm",
                "inputs": _llm_input_messages(question),
                "outputs": _llm_output_messages("", [tc_obj]),
                "error": None,
                "extra": {"metadata": {"ls_model_name": MODEL_NAME, "ls_model_type": "chat"}},
                "tags": tags,
                "start_time": llm_start.isoformat(),
                "end_time": llm_end_1.isoformat(),
            }
        )

        # Tool run
        tool_output = TOOL_OUTPUTS[tool_name](tool_args)
        runs.append(
            {
                "id": tool_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": tool_name,
                "run_type": "tool",
                "inputs": tool_args,
                "outputs": tool_output,
                "error": None,
                "extra": None,
                "tags": tags,
                "start_time": tool_start.isoformat(),
                "end_time": tool_end.isoformat(),
            }
        )

        # LLM run 2 (final answer)
        runs.append(
            {
                "id": llm2_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": "ChatOpenAI",
                "run_type": "llm",
                "inputs": _llm_input_messages(question),
                "outputs": _llm_output_messages(response),
                "error": None,
                "extra": {"metadata": {"ls_model_name": MODEL_NAME, "ls_model_type": "chat"}},
                "tags": tags,
                "start_time": llm2_start.isoformat(),
                "end_time": llm2_end.isoformat(),
            }
        )
    else:
        # Simple: single LLM call, no tool
        llm_end = llm_start + timedelta(milliseconds=random.randint(500, 1500))
        root_end = llm_end + timedelta(milliseconds=random.randint(5, 30))

        runs.append(
            {
                "id": llm_id,
                "trace_id": trace_id,
                "parent_run_id": root_id,
                "name": "ChatOpenAI",
                "run_type": "llm",
                "inputs": _llm_input_messages(question),
                "outputs": _llm_output_messages(response),
                "error": None,
                "extra": {"metadata": {"ls_model_name": MODEL_NAME, "ls_model_type": "chat"}},
                "tags": tags,
                "start_time": llm_start.isoformat(),
                "end_time": llm_end.isoformat(),
            }
        )

    # Build the full conversation message list for outputs.messages
    system_msg = {
        "role": "system",
        "content": (
            "You are a helpful customer support agent for ACME Industries. "
            "Answer questions about our products: Anvils, Rocket Skates, "
            "Giant Magnets, Portable Holes, and Earthquake Pills."
        ),
    }
    user_msg = {"role": "user", "content": question}

    if include_tool:
        conversation_messages = [
            system_msg,
            user_msg,
            # Assistant decides to call a tool
            {"role": "assistant", "content": "", "tool_calls": [tc_obj]},
            # Tool result
            {
                "role": "tool",
                "content": tool_output["output"],
                "name": tool_name,
                "tool_call_id": tc_obj["id"],
            },
            # Final assistant response
            {"role": "assistant", "content": response},
        ]
    else:
        conversation_messages = [
            system_msg,
            user_msg,
            {"role": "assistant", "content": response},
        ]

    # Root chain run (always first when sorted by parent_run_id is None)
    root_run = {
        "id": root_id,
        "trace_id": trace_id,
        "parent_run_id": None,
        "name": "ACME Support",
        "run_type": "chain",
        "inputs": {"question": question},
        "outputs": {
            "messages": conversation_messages,
            "output": response,
        },
        "error": None,
        "extra": {"metadata": {"product_line": product, "subtopic": subtopic}},
        "tags": tags,
        "start_time": root_start.isoformat(),
        "end_time": root_end.isoformat(),
    }

    return [root_run] + runs


# ---------------------------------------------------------------------------
# Variable substitution
# ---------------------------------------------------------------------------
def fill_template(template: str, product: str) -> str:
    """Replace placeholders in a template string."""
    replacements = {
        "{order_id}": _order_id(),
        "{name}": _name(),
        "{state}": _state(),
        "{city}": _city(),
        "{weight}": random.choice(ANVIL_WEIGHTS),
        "{magnet_strength}": random.choice(MAGNET_STRENGTHS),
        "{hole_size}": random.choice(HOLE_SIZES),
        "{quake_rating}": random.choice(QUAKE_RATINGS),
        "{speed_low}": random.choice(SKATE_SPEEDS[:2]),
        "{speed_high}": random.choice(SKATE_SPEEDS[-2:]),
    }
    result = template
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------
def generate_traces(seed: int = 42) -> list[dict]:
    random.seed(seed)
    all_runs: list[dict] = []

    base_time = datetime(2025, 3, 10, 8, 0, 0, tzinfo=timezone.utc)

    for product, count in PRODUCT_DISTRIBUTION:
        subtopics = list(TEMPLATES[product].keys())
        # Distribute traces roughly evenly across subtopics
        per_subtopic = count // len(subtopics)
        remainder = count % len(subtopics)

        subtopic_counts = [per_subtopic] * len(subtopics)
        for i in range(remainder):
            subtopic_counts[i] += 1

        for subtopic, sub_count in zip(subtopics, subtopic_counts):
            templates = TEMPLATES[product][subtopic]
            for i in range(sub_count):
                # Pick a template (cycle through, then randomize)
                tmpl = templates[i % len(templates)]
                q_template, r_template, tool_name = tmpl

                # Fill in variables (same seed for both Q and R so IDs match)
                shared_replacements = {
                    "{order_id}": _order_id(),
                    "{name}": _name(),
                    "{state}": _state(),
                    "{city}": _city(),
                    "{weight}": random.choice(ANVIL_WEIGHTS),
                    "{magnet_strength}": random.choice(MAGNET_STRENGTHS),
                    "{hole_size}": random.choice(HOLE_SIZES),
                    "{quake_rating}": random.choice(QUAKE_RATINGS),
                    "{speed_low}": random.choice(SKATE_SPEEDS[:2]),
                    "{speed_high}": random.choice(SKATE_SPEEDS[-2:]),
                }
                question = q_template
                response = r_template
                for key, value in shared_replacements.items():
                    question = question.replace(key, value)
                    response = response.replace(key, value)

                # Stagger traces over time
                trace_time = base_time + timedelta(
                    minutes=random.randint(0, 1440),  # spread over 1 day
                    seconds=random.randint(0, 59),
                )

                trace_runs = build_trace(
                    product=product,
                    subtopic=subtopic,
                    question=question,
                    response=response,
                    tool_name=tool_name,
                    base_time=trace_time,
                )
                all_runs.extend(trace_runs)

    return all_runs


def main():
    runs = generate_traces()

    # Count traces (unique trace_ids)
    trace_ids = {r["trace_id"] for r in runs}
    product_counts: dict[str, int] = {}
    for r in runs:
        if r["parent_run_id"] is None:  # root runs
            product = r["extra"]["metadata"]["product_line"]
            product_counts[product] = product_counts.get(product, 0) + 1

    print(f"Generated {len(runs)} runs across {len(trace_ids)} traces")
    print("\nProduct distribution:")
    for product, count in sorted(product_counts.items(), key=lambda x: -x[1]):
        pct = count / len(trace_ids) * 100
        print(f"  {product}: {count} ({pct:.1f}%)")

    output_path = "module2_traces.json"
    with open(output_path, "w") as f:
        json.dump(runs, f, indent=2, default=str)
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
