# GEE Authentication & Setup Guide
# BAH 2026 PS6 — Run this before anything else

# ============================================================
# STEP 0: PREREQUISITES
# ============================================================
# You need:
#   - A Google account
#   - Python 3.9+ installed
#   - pip available
#   - Internet connection

# Check your Python version first:
python --version        # Must be 3.9 or higher
pip --version

# ============================================================
# STEP 1: REGISTER FOR GOOGLE EARTH ENGINE
# ============================================================
# 1. Go to: https://earthengine.google.com
# 2. Click "Get Started" (top right)
# 3. Sign in with your Google account
# 4. Select: "Unpaid usage" → "Academia and Research"
# 5. Fill out the form — use your college email if possible
# 6. Approval is usually INSTANT but can take up to 24 hours
#
# ALL 4 TEAM MEMBERS must do this separately.
# Each person needs their own GEE account.
#
# Once approved, verify by visiting:
# https://code.earthengine.google.com
# If you see the GEE Code Editor — you're approved.

# ============================================================
# STEP 2: CREATE A GEE CLOUD PROJECT
# ============================================================
# Recent GEE versions (0.1.370+) require a Cloud Project ID.
#
# 1. Go to: https://console.cloud.google.com
# 2. Create a new project (or use existing)
#    Name it something like: bah2026-ps6
#    Note your Project ID (looks like: bah2026-ps6 or bah2026-ps6-123456)
# 3. Go to: https://console.cloud.google.com/apis/library
#    Search "Earth Engine API" → Enable it for your project
#
# You will use this Project ID in: ee.Initialize(project='YOUR_PROJECT_ID')

# ============================================================
# STEP 3: INSTALL DEPENDENCIES
# ============================================================

pip install earthengine-api>=0.1.390 geemap>=0.30.0

# Verify:
python -c "import ee; import geemap; print('ee:', ee.__version__, '| geemap:', geemap.__version__)"

# ============================================================
# STEP 4: AUTHENTICATE
# ============================================================

# Run this in your terminal (NOT inside a Python script):
earthengine authenticate

# What happens:
# 1. A browser window opens automatically
# 2. Sign in with the Google account that has GEE access
# 3. Click "Allow"
# 4. Copy the authorization code
# 5. Paste it back in the terminal
# 6. You see: "Successfully saved authorization token."
#
# This saves credentials at: ~/.config/earthengine/credentials
# You only need to do this ONCE per machine.

# ============================================================
# STEP 5: VERIFY AUTHENTICATION
# ============================================================
# Run this Python snippet. If it prints without error — you're done.

python3 << 'VERIFY'
import ee

# Replace with your actual GEE Cloud Project ID
PROJECT_ID = "python3 << 'VERIFY'
import ee

# Replace with your actual GEE Cloud Project ID
PROJECT_ID = "your-project-id-here"

try:
    ee.Initialize(project=PROJECT_ID)
    print("✓ GEE initialized successfully")
    print("  Project:", PROJECT_ID)
except Exception as e:
    print("✗ GEE init failed:", e)
    print("  → Check your Project ID and that Earth Engine API is enabled")
    exit(1)

# Test: count Sentinel-2 images over our pilot area
aoi = ee.Geometry.Point([79.8, 16.5])
count = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
         .filterBounds(aoi)
         .filterDate("2024-06-01", "2024-11-30")
         .size()
         .getInfo())
print(f"✓ Sentinel-2 images over Nagarjunasagar (Kharif 2024): {count}")

if count > 0:
    print("  → Data confirmed. You are ready to run the pipeline.")
else:
    print("  → WARNING: 0 images found. Check your AOI or date range.")
VERIFY"

try:
    ee.Initialize(project=PROJECT_ID)
    print("✓ GEE initialized successfully")
    print("  Project:", PROJECT_ID)
except Exception as e:
    print("✗ GEE init failed:", e)
    print("  → Check your Project ID and that Earth Engine API is enabled")
    exit(1)

# Test: count Sentinel-2 images over our pilot area
aoi = ee.Geometry.Point([79.8, 16.5])
count = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
         .filterBounds(aoi)
         .filterDate("2024-06-01", "2024-11-30")
         .size()
         .getInfo())
print(f"✓ Sentinel-2 images over Nagarjunasagar (Kharif 2024): {count}")

if count > 0:
    print("  → Data confirmed. You are ready to run the pipeline.")
else:
    print("  → WARNING: 0 images found. Check your AOI or date range.")
VERIFY

# ============================================================
# COMMON ERRORS AND FIXES
# ============================================================
#
# Error: "Please authorize access to your Earth Engine account"
# Fix:   Run `earthengine authenticate` again
#
# Error: "Project not found" or "404"
# Fix:   Check your Project ID at console.cloud.google.com
#        Make sure Earth Engine API is enabled for that project
#
# Error: "EEException: Too many concurrent aggregations"
# Fix:   Add tileScale=4 to sampleRegions() calls. Already done in our scripts.
#
# Error: "Cannot find credentials"
# Fix:   Run `earthengine authenticate` — credentials file is missing
#        Expected location: ~/.config/earthengine/credentials
#
# Error: ModuleNotFoundError: No module named 'ee'
# Fix:   pip install earthengine-api
#
# ============================================================
# FOR GOOGLE COLAB USERS (alternative to local setup)
# ============================================================
#
# If local setup is painful, use Colab — it's simpler:
#
#   !pip install earthengine-api geemap -q
#   import ee
#   ee.Authenticate()        # Opens a link, no terminal needed
#   ee.Initialize(project='your-project-id')
#
# Colab is fine for development and the hackathon demo.
# Use local Python for the final pipeline.
