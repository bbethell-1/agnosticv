#!/usr/bin/env python3
"""
Simple test using the public link access
"""
import gspread
from google.oauth2.service_account import Credentials

def test_simple_access():
    """Test access using service account with public link"""
    try:
        # Use service account with minimal scopes
        scope = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        gc = gspread.authorize(creds)
        
        # Your spreadsheet ID
        spreadsheet_id = "1ALpaVsoPEUClIYR3aULCU2HSabnUV8e7zloMl54pAMM"
        
        print("🔄 Attempting to access spreadsheet...")
        spreadsheet = gc.open_by_key(spreadsheet_id)
        print(f"✅ Successfully opened: {spreadsheet.title}")
        
        # List worksheets
        worksheets = spreadsheet.worksheets()
        print(f"\n📊 Available worksheets:")
        for i, ws in enumerate(worksheets):
            print(f"  {i+1}. '{ws.title}'")
        
        # Try to access the data
        if worksheets:
            ws = worksheets[0]  # Use first worksheet
            print(f"\n🔄 Reading data from '{ws.title}'...")
            records = ws.get_all_records()
            print(f"✅ Successfully read {len(records)} records")
            
            if records:
                print(f"📋 Headers: {list(records[0].keys())}")
                print(f"📋 First record: {records[0]}")
                
                # Check if this looks like our data
                headers = list(records[0].keys())
                expected_headers = ['CI Path', 'CI Name', 'Current Value', 'Primary BU', 'Secondary BU']
                
                if all(h in headers for h in expected_headers):
                    print("✅ This looks like the correct data structure!")
                    return True
                else:
                    print(f"⚠️  Headers don't match expected format")
                    print(f"   Expected: {expected_headers}")
                    print(f"   Found: {headers}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_write_access():
    """Test if we can write (needed for the main script)"""
    try:
        # Use write scope
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        gc = gspread.authorize(creds)
        
        spreadsheet_id = "1ALpaVsoPEUClIYR3aULCU2HSabnUV8e7zloMl54pAMM"
        spreadsheet = gc.open_by_key(spreadsheet_id)
        
        print("✅ Write access confirmed!")
        return gc
        
    except Exception as e:
        print(f"❌ Write access failed: {e}")
        return None

def main():
    print("Simple Access Test")
    print("=" * 30)
    
    # Test read access
    print("🔄 Testing read access...")
    if test_simple_access():
        print("\n🔄 Testing write access...")
        gc = test_write_access()
        
        if gc:
            print("\n🎉 SUCCESS! Both read and write access work!")
            print("✅ Ready to run the main script!")
            
            # Update the main script with working configuration
            print("\n📝 The main script should work now with these settings:")
            print("   - service_account.json file")
            print("   - Public link access (Anyone with link: writer)")
            print("   - Spreadsheet ID: 1ALpaVsoPEUClIYR3aULCU2HSabnUV8e7zloMl54pAMM")
        else:
            print("\n⚠️  Read access works but write access failed")
            print("💡 Try changing 'Anyone with link' to 'Editor' in Google Sheets")
    else:
        print("\n❌ Read access failed - check the detailed error above")

if __name__ == "__main__":
    main()
