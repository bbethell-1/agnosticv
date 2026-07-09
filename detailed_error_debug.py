#!/usr/bin/env python3
"""
Detailed error debugging to see exactly what's failing
"""
import gspread
from google.oauth2.service_account import Credentials
import traceback

def debug_spreadsheet_access():
    """Debug every step of spreadsheet access"""
    try:
        print("🔄 Step 1: Loading service account credentials...")
        scope = ['https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        print("✅ Credentials loaded successfully")
        
        print("🔄 Step 2: Authorizing gspread client...")
        gc = gspread.authorize(creds)
        print("✅ Client authorized successfully")
        
        print("🔄 Step 3: Extracting spreadsheet ID from URL...")
        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1ALpaVsoPEUClIYR3aULCU2HSabnUV8e7zloMl54pAMM/edit?usp=sharing"
        spreadsheet_id = spreadsheet_url.split('/d/')[1].split('/')[0]
        print(f"✅ Spreadsheet ID: {spreadsheet_id}")
        
        print("🔄 Step 4: Opening spreadsheet by key...")
        spreadsheet = gc.open_by_key(spreadsheet_id)
        print(f"✅ Opened spreadsheet: '{spreadsheet.title}'")
        
        print("🔄 Step 5: Getting list of worksheets...")
        worksheets = spreadsheet.worksheets()
        print(f"✅ Found {len(worksheets)} worksheets:")
        for i, ws in enumerate(worksheets):
            print(f"   {i+1}. '{ws.title}'")
        
        print("🔄 Step 6: Looking for 'reportinglabels' worksheet...")
        worksheet_names = [ws.title for ws in worksheets]
        
        # Check exact match
        if 'reportinglabels' in worksheet_names:
            print("✅ Found 'reportinglabels' worksheet")
            worksheet = spreadsheet.worksheet('reportinglabels')
        else:
            print("❌ 'reportinglabels' worksheet not found")
            print("🔍 Available worksheet names (check for typos):")
            for name in worksheet_names:
                print(f"   - '{name}' (length: {len(name)})")
            
            # Try to find close matches
            close_matches = [name for name in worksheet_names if 'reporting' in name.lower() or 'label' in name.lower()]
            if close_matches:
                print(f"🔍 Possible matches: {close_matches}")
                worksheet = spreadsheet.worksheet(close_matches[0])
                print(f"✅ Using worksheet: '{worksheet.title}'")
            else:
                # Use first worksheet as fallback
                worksheet = worksheets[0]
                print(f"⚠️  Using first worksheet as fallback: '{worksheet.title}'")
        
        print("🔄 Step 7: Reading all records...")
        records = worksheet.get_all_records()
        print(f"✅ Successfully read {len(records)} records")
        
        if records:
            print("🔄 Step 8: Analyzing data structure...")
            first_record = records[0]
            headers = list(first_record.keys())
            print(f"📋 Headers found: {headers}")
            print(f"📋 First record: {first_record}")
            
            # Check for expected columns
            expected_cols = ['CI Path', 'CI Name', 'Primary BU', 'Secondary BU']
            missing_cols = [col for col in expected_cols if col not in headers]
            if missing_cols:
                print(f"⚠️  Missing expected columns: {missing_cols}")
            else:
                print("✅ All expected columns found!")
        else:
            print("⚠️  No data found in worksheet")
        
        print("\n🎉 SUCCESS! Spreadsheet access is working!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR at step: {e}")
        print("\n🔍 Full error traceback:")
        traceback.print_exc()
        return False

def main():
    print("Detailed Error Debugging")
    print("=" * 40)
    
    debug_spreadsheet_access()

if __name__ == "__main__":
    main()
