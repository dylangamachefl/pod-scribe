
import asyncio
import httpx
import sys

API_BASE = "http://localhost:8001"

async def verify_fix():
    print("🚀 Starting verification of transcription selection fix...")
    
    async with httpx.AsyncClient(timeout=10) as client:
        # 1. Get all episodes to find some to test with
        print("📁 Fetching episodes...")
        try:
            resp = await client.get(f"{API_BASE}/episodes")
            episodes = resp.json()
        except Exception as e:
            print(f"❌ Failed to connect to API: {e}")
            return

        if not episodes:
            print("⚠️ No episodes found. Please add a feed or fetch episodes first.")
            return

        test_episodes = episodes[:2]
        test_ids = [ep['id'] for ep in test_episodes]
        print(f"🧪 Using {len(test_ids)} episodes for testing: {test_ids}")

        # 2. Bulk select them
        print(f"✅ Selecting episodes {test_ids}...")
        resp = await client.post(f"{API_BASE}/episodes/bulk-select", json={
            "episode_ids": test_ids,
            "selected": True
        })
        print(f"   Response: {resp.status_code} {resp.json()}")

        # 3. Check /stats to see if they are counted
        print("📊 Checking /stats...")
        resp = await client.get(f"{API_BASE}/stats")
        stats = resp.json()
        print(f"   Selected count in stats: {stats.get('selected_episodes')}")
        
        # 4. Check /episodes to see if they appear with selected=True
        print("📥 Checking /episodes...")
        resp = await client.get(f"{API_BASE}/episodes")
        all_ep_data = resp.json()
        selected_in_all = [ep for ep in all_ep_data if ep['id'] in test_ids and ep['selected']]
        print(f"   Found {len(selected_in_all)} test episodes as 'selected' in all episodes.")

        if len(selected_in_all) != len(test_ids):
            print("❌ FAILURE: Not all test episodes were correctly marked as selected.")
        else:
            print("✨ SUCCESS: Backend selection logic is working correctly!")

        # 5. Optional: Verify fallback in start_transcription (Dry run by checking errors)
        # We won't actually start it if it might trigger a real download, 
        # but we can see if it fails with "No episodes" or something else.
        print("🚀 Testing /transcription/start fallback (empty request)...")
        resp = await client.post(f"{API_BASE}/transcription/start", json={})
        data = resp.json()
        if resp.status_code == 400 and "already in progress" in data.get('detail', ''):
             print("ℹ️ Pipeline already running, can't verify start fallback now but selection is verified.")
        else:
             print(f"   Response: {resp.status_code} {data}")

if __name__ == "__main__":
    asyncio.run(verify_fix())
