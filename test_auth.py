#!/usr/bin/env python3
"""
Test script to verify Google Sheets authentication
"""
import os
import gspread
from google.auth import default
from google.oauth2.service_account import Credentials

def test_authentication():
    """Test Google Sheets authentication"""
    
    # Method 1: Try OAuth2 credentials
    oauth_file = "credentials.json"
    if os.path.exists(oauth_file):
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            import pickle
            
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
                     'https://www.googleapis.com/auth/drive.readonly']
            
            creds = None
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(oauth_file, SCOPES)
                    creds = flow.run_local_server(port=0)
                
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            
            gc = gspread.authorize(creds)
            print("✅ OAuth2 authentication successful!")
            return gc
            
        except Exception as e:
            print(f"❌ OAuth2 authentication failed: {e}")
    
    # Method 2: Try service account
    service_file = "service_account.json"
    if os.path.exists(service_file):
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(service_file, scopes=scope)
            gc = gspread.authorize(creds)
            print("✅ Service account authentication successful!")
            return gc
        except Exception as e:
            print(f"❌ Service account authentication failed: {e}")
    
    print("❌ No valid authentication method found")
    return None

def test_spreadsheet_access(gc, spreadsheet_url):
    """Test access to the specific spreadsheet"""
    try:
        # Extract spreadsheet ID
        spreadsheet_id = spreadsheet_url.split('/d/')[1].split('/')[0]
        spreadsheet = gc.open_by_key(spreadsheet_id)
        
        print(f"✅ Successfully opened spreadsheet: {spreadsheet.title}")
        
        # Try to access the reportinglabels worksheet
        worksheet = spreadsheet.worksheet('reportinglabels')
        print(f"✅ Successfully accessed worksheet: {worksheet.title}")
        
        # Get a sample of data
        records = worksheet.get_all_records()
        print(f"✅ Successfully read {len(records)} records")
        
        if records:
            print(f"✅ Sample record: {records[0]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Spreadsheet access failed: {e}")
        return False

def main():
    print("Testing Google Sheets Authentication")
    print("=" * 40)
    
    # Test authentication
    gc = test_authentication()
    if not gc:
        print("\n💡 Make sure you have either:")
        print("   - credentials.json (OAuth2)")
        print("   - service_account.json (Service Account)")
        return
    
    # Test spreadsheet access
    print("\nTesting spreadsheet access...")
    spreadsheet_url = input("Enter your Google Sheets URL: ").strip()
    
    if test_spreadsheet_access(gc, spreadsheet_url):
        print("\n🎉 All tests passed! You're ready to run the main script.")
    else:
        print("\n❌ Spreadsheet access failed. Check the URL and permissions.")

if __name__ == "__main__":
    main()
