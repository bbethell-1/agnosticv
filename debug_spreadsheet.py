#!/usr/bin/env python3
"""
Detailed permission debugging for Google Sheets
"""
import os
import gspread
from google.oauth2.service_account import Credentials
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def get_service_account_info():
    """Get detailed service account information"""
    service_file = "service_account.json"
    if os.path.exists(service_file):
        with open(service_file, 'r') as f:
            data = json.load(f)
        return data
    return None

def test_drive_api_access():
    """Test Google Drive API access to check permissions"""
    try:
        service_data = get_service_account_info()
        if not service_data:
            print("❌ No service account file found")
            return False
        
        scope = ['https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        
        # Build Drive API service
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Test basic access
        results = drive_service.files().list(pageSize=1).execute()
        print("✅ Google Drive API access successful")
        
        return drive_service
        
    except Exception as e:
        print(f"❌ Drive API access failed: {e}")
        return None

def check_file_permissions(drive_service, spreadsheet_id):
    """Check specific file permissions"""
    try:
        # Get file metadata
        file_metadata = drive_service.files().get(fileId=spreadsheet_id).execute()
        print(f"📋 File name: {file_metadata.get('name')}")
        print(f"👤 File owner: {file_metadata.get('owners', [{}])[0].get('emailAddress', 'Unknown')}")
        
        # Get permissions
        permissions = drive_service.permissions().list(fileId=spreadsheet_id).execute()
        
        print(f"\n🔒 Current permissions:")
        for perm in permissions.get('permissions', []):
            perm_type = perm.get('type', 'unknown')
            role = perm.get('role', 'unknown')
            email = perm.get('emailAddress', 'N/A')
            
            if perm_type == 'anyone':
                print(f"  📢 Anyone with link: {role}")
            elif perm_type == 'user':
                print(f"  👤 User ({email}): {role}")
            elif perm_type == 'group':
                print(f"  👥 Group ({email}): {role}")
            else:
                print(f"  ❓ {perm_type} ({email}): {role}")
        
        return True
        
    except HttpError as e:
        if e.resp.status == 403:
            print("❌ Permission denied - service account cannot access this file")
            print("💡 Make sure the service account email is shared with Editor access")
        else:
            print(f"❌ HTTP Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking permissions: {e}")
        return False

def test_alternative_access():
    """Try alternative access methods"""
    print("\n🔄 Testing alternative access methods...")
    
    # Try with different scopes
    try:
        # More permissive scopes
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.file'
        ]
        creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
        gc = gspread.authorize(creds)
        
        spreadsheet_id = "1ALpaVsoPEUClIYR3aULCU2HSabnUV8e7zloMl54pAMM"
        spreadsheet = gc.open_by_key(spreadsheet_id)
        print("✅ Success with expanded scopes!")
        return True
        
    except Exception as e:
        print(f"❌ Failed with expanded scopes: {e}")
    
    # Try accessing by URL instead of ID
    try:
        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1ALpaVsoPEUClIYR3aULCU2HSabnUV8e7zloMl54pAMM/edit?usp=sharing"
        spreadsheet = gc.open_by_url(spreadsheet_url)
        print("✅ Success with URL access!")
        return True
        
    except Exception as e:
        print(f"❌ Failed with URL access: {e}")
    
    return False

def main():
    print("Detailed Permission Debugging")
    print("=" * 40)
    
    # Show service account details
    service_data = get_service_account_info()
    if service_data:
        print(f"📧 Service account: {service_data.get('client_email')}")
        print(f"📝 Project: {service_data.get('project_id')}")
        print(f"🔑 Key ID: {service_data.get('private_key_id', 'Unknown')}")
    
    # Test Drive API access
    print(f"\n🔄 Testing Google Drive API access...")
    drive_service = test_drive_api_access()
    
    if drive_service:
        # Check specific file permissions
        spreadsheet_id = "1ALpaVsoPEUClIYR3aULCU2HSabnUV8e7zloMl54pAMM"
        print(f"\n🔄 Checking permissions for spreadsheet...")
        check_file_permissions(drive_service, spreadsheet_id)
    
    # Test alternative access methods
    test_alternative_access()
    
    print(f"\n💡 TROUBLESHOOTING TIPS:")
    print(f"1. Verify the service account email is exactly: {service_data.get('client_email') if service_data else 'Unknown'}")
    print(f"2. Make sure you clicked 'Send' after adding the email in Google Sheets")
    print(f"3. Try removing and re-adding the service account email")
    print(f"4. Check if the spreadsheet is in a shared drive (requires different permissions)")
    print(f"5. Wait a few minutes - permission changes can take time to propagate")

if __name__ == "__main__":
    main()
