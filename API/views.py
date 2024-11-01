from django.shortcuts import render

# Create your views here.
import requests
import base64
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import os
import re
import logging
from google.oauth2 import service_account
from googleapiclient.http import MediaInMemoryUpload
from django.conf import settings












# Authenticate and create a Google Drive service instance
def authenticate_google_drive():
    # Replace 'key.json' with the actual path to your key.json file
    credentials = Credentials.from_service_account_file('API//key.json', scopes=["https://www.googleapis.com/auth/drive"])
    drive_service = build('drive', 'v3', credentials=credentials)
    return drive_service

# Function to fetch project details from SiteCapture API
def get_project_details(project_id, headers):
    url = f"https://api.sitecapture.com/customer_api/2_0/project/{project_id}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()  # Return project data in JSON format
    else:
        print(f"Failed to fetch project details: {response.status_code}, {response.text}")
        return None

# Function to extract media IDs section-wise from project details
def extract_media_ids(project_data):
    media_dict = {}
    
    for item in project_data.get('fields', []):
        section_key = item.get('section_key')
        media_list = item.get('media', [])
        
        # Store media IDs section-wise
        if media_list:
            if section_key not in media_dict:
                media_dict[section_key] = []
            for media in media_list:
                media_dict[section_key].append(media.get('id'))
    
    return media_dict

# Function to download image data from SiteCapture
def get_image_data(media_id, headers):
    sitecapture_url = f'https://api.sitecapture.com/customer_api/1_0/media/image/{media_id}'
    response = requests.get(sitecapture_url, headers=headers)
    
    if response.status_code == 200:
        return response.content  # Return binary image data
    else:
        print(f"Failed to retrieve image data: {response.status_code}, {response.text}")
        return None

# Function to upload image to Google Drive and make it public
def upload_to_google_drive(drive_service, image_data, filename):
    # Convert the image binary data into a file-like object
    image_stream = io.BytesIO(image_data)
    media = MediaIoBaseUpload(image_stream, mimetype='image/jpeg')
    
    # File metadata, such as the file name
    file_metadata = {'name': filename}
    
    # Upload the file to Google Drive
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    
    # Get the file ID of the uploaded image
    file_id = file.get('id')
    
    # Make the file public by setting permissions
    permission = {
        'type': 'anyone',
        'role': 'reader'
    }
    
    drive_service.permissions().create(
        fileId=file_id,
        body=permission
    ).execute()
    
    # Return the public URL of the file
    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

# Function to post the section-wise image URLs to Podio webhook
def post_to_podio(webhook_url, data):
    headers = {
        'Content-Type': 'application/json'
    }
    
    response = requests.post(webhook_url, json=data, headers=headers)
    if response.status_code == 200:
        print("Successfully posted to Podio webhook.")
    else:
        print(f"Failed to post to Podio webhook: {response.status_code}, {response.text}")

class ProjectImageUploadView(APIView):
    def post(self, request, *args, **kwargs):
        project_id = request.data.get('project_id')

        if not project_id:
            return Response({"error": "Project ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Step 1: Set up the headers for authorization
            headers = {
                'Authorization': 'Basic YXBwbGljYXRpb25zQG15LXNtYXJ0aG91c2UuY29tOmFkbWluNG15c21hcnRob3VzZQ',  # Replace with actual auth
                'API_KEY': 'NVN6IIEZ4DZE'  # Replace with actual API key
            }

            # Authenticate Google Drive
            drive_service = authenticate_google_drive()

            # Step 2: Fetch project details from SiteCapture
            project_data = get_project_details(project_id, headers)

            if not project_data:
                return Response({"error": "Failed to fetch project details."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Step 3: Extract media IDs section-wise
            media_ids_by_section = extract_media_ids(project_data)

            # Step 4: For each media ID, download the image, upload to Google Drive, and store the URLs section-wise
            section_image_urls = {}

            for section, media_ids in media_ids_by_section.items():
                section_image_urls[section] = []
                
                for media_id in media_ids:
                    # Download the image
                    image_data = get_image_data(media_id, headers)
                    if image_data:
                        # Upload the image to Google Drive and get the URL
                        image_url = upload_to_google_drive(drive_service, image_data, f"media_{media_id}.jpg")
                        
                        # Add the image URL to the section
                        section_image_urls[section].append({
                            "media_id": media_id,
                            "url": image_url
                        })

            # Step 5: Post the section-wise image URLs to Podio webhook
            podio_webhook_url = "https://workflow-automation.podio.com/catch/lzy6tsm2irt48l9"  # Replace with actual webhook URL
            post_to_podio(podio_webhook_url, section_image_urls)

            return Response({"success": "Images uploaded and webhook posted successfully.", "data": section_image_urls}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





import os
import requests
import re
import logging
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaInMemoryUpload
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

# Google Drive API Scopes
SCOPES = ['https://www.googleapis.com/auth/drive']

# Set up basic logging
logging.basicConfig(level=logging.INFO)

class PodioGoogleDriveView(APIView):
    def authenticate_podio(self):
        url = 'https://podio.com/oauth/token'
        data = {
            'grant_type': 'password',
            'client_id': "",
            'client_secret': "",
            'username': "",
            'password': ""
        }
        response = requests.post(url, data=data)
        response.raise_for_status()  # Ensure an exception is raised if authentication fails
        return response.json()['access_token']

    def fetch_podio_site_survey_data(self, podio_access_token, podio_item_id):
        url = f"https://api.podio.com/item/{podio_item_id}"
        headers = {'Authorization': f'Bearer {podio_access_token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def extract_drive_links(self, site_survey_data):
        drive_links = []
        for field in site_survey_data['fields']:
            for value in field['values']:
                if isinstance(value, dict) and 'embed' in value:
                    embed_url = value['embed'].get('original_url', '')
                    if 'drive.google.com' in embed_url:
                        drive_links.append(embed_url)
        return drive_links

    def resolve_drive_download_link(self, drive_link):
        file_id_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', drive_link)
        if file_id_match:
            file_id = file_id_match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        return None

    def authenticate_google_drive(self):
        creds = service_account.Credentials.from_service_account_file('API//client_secret.json', scopes=SCOPES
        )
        return creds

    def extract_project_details(self, site_survey_data):
        project_name = address = None
        for field in site_survey_data['fields']:
            if field['label'] == 'Project Name':
                project_name = field['values'][0]['value']
            elif field['label'] == 'Address':
                address = field['values'][0]['value']
        if not project_name or not address:
            raise ValueError("Project name or address missing in Podio data")
        return project_name, address

    def search_folder(self, service, folder_name, parent_folder_id):
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_folder_id}' in parents"
        response = service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
        files = response.get('files', [])
        return files[0]['id'] if files else None

    def create_folder(self, service, parent_folder_id, folder_name):
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

    def upload_file_to_drive(self, service, file_name, file_content, folder_id):
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        media = MediaInMemoryUpload(file_content, mimetype='application/octet-stream')
        service.files().create(body=file_metadata, media_body=media).execute()

    def post(self, request, *args, **kwargs):
        try:
            # Authenticate and get Podio item data
            podio_access_token = self.authenticate_podio()
            data = request.data
            podio_item_id = data.get('podio_item_id')
            if not podio_item_id:
                return Response({'error': 'podio_item_id is required'}, status=status.HTTP_400_BAD_REQUEST)
                
            site_survey_data = self.fetch_podio_site_survey_data(podio_access_token, podio_item_id)

            # Get project details
            project_name, address = self.extract_project_details(site_survey_data)
            creds = self.authenticate_google_drive()
            service = build('drive', 'v3', credentials=creds)

            # Define main and subfolder names
            parent_folder_id = ""
            main_folder_name = f"{project_name}-{address}"
            subfolder_name = "SiteCapture Site Survey Images"

            # Check if main folder exists or create it
            main_folder_id = self.search_folder(service, main_folder_name, parent_folder_id) or \
                             self.create_folder(service, parent_folder_id, main_folder_name)

            # Check if subfolder exists or create it
            subfolder_id = self.search_folder(service, subfolder_name, main_folder_id) or \
                           self.create_folder(service, main_folder_id, subfolder_name)

            # Process and upload each image link as a standalone file
            drive_links = self.extract_drive_links(site_survey_data)
            for link in drive_links:
                download_link = self.resolve_drive_download_link(link)
                if download_link:
                    file_content = requests.get(download_link).content
                    file_name = link.split('/')[-1] + ".jpg"  # Adjust naming if needed
                    self.upload_file_to_drive(service, file_name, file_content, subfolder_id)

            return Response({'status': 'success', 'folder_id': subfolder_id})

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
