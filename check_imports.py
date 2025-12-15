import sys
import os

# Simulate PYTHONPATH adjustments
# In the containers, we mount ./shared to /app/shared.
# PYTHONPATH includes /app/shared.
# So if we are in root and want to simulate that, we add ./shared to sys.path.

sys.path.append(os.path.join(os.getcwd(), 'shared'))

try:
    import podcast_transcriber_shared.events
    print("Successfully imported podcast_transcriber_shared.events")
except ImportError as e:
    print(f"Failed to import podcast_transcriber_shared.events: {e}")

try:
    import podcast_transcriber_shared.database
    print("Successfully imported podcast_transcriber_shared.database")
except ImportError as e:
    print(f"Failed to import podcast_transcriber_shared.database: {e}")
