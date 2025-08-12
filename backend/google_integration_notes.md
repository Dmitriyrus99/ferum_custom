## Google Integration Notes

To enable full Google Drive and Google Sheets integration, you need to:

1.  **Set up a Google Cloud Project:**
    *   Go to the Google Cloud Console.
    *   Create a new project or select an existing one.

2.  **Enable APIs:**
    *   Enable the Google Drive API.
    *   Enable the Google Sheets API.

3.  **Create Credentials:**
    *   Create a Service Account. Download the JSON key file. This file contains your `client_email` and `private_key`.
    *   Alternatively, for user-based authentication (e.g., if users need to authorize access to their own Drive/Sheets), set up OAuth 2.0 Client IDs.

4.  **Share Google Sheets/Drive Folders:**
    *   If using a Service Account, share the relevant Google Sheets and Google Drive folders with the Service Account's email address.

5.  **Configure Environment Variables:**
    *   Update your `.env` file (or environment variables) with the necessary Google credentials. For example:
        ```
        GOOGLE_SERVICE_ACCOUNT_EMAIL="your-service-account-email@your-project-id.iam.gserviceaccount.com"
        GOOGLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
        GOOGLE_SHEETS_SPREADSHEET_ID="your-spreadsheet-id"
        GOOGLE_DRIVE_FOLDER_ID="your-drive-folder-id"
        ```
        (Note: The `GOOGLE_PRIVATE_KEY` should be the actual private key string, with `\n` for newlines, or loaded from a file.)

6.  **Implement Integration Logic:**
    *   The placeholders in `ferum_custom/ferum_custom/doctype/CustomAttachment/custom_attachment.py` and `ferum_custom/ferum_custom/doctype/Invoice/invoice.py` need to be replaced with actual Python code using libraries like `google-api-python-client` or `gspread` to interact with Google APIs.

**Important:** Keep your Google API credentials secure and do not expose them publicly.
