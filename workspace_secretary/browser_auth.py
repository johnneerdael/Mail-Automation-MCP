"""Browser-based OAuth2 authentication for Gmail."""

import base64
import json
import logging
import os
import secrets
import sys
import time
import webbrowser
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urlencode, urlparse, parse_qs

import yaml
from flask import Flask, request, redirect, url_for

from workspace_secretary.config import OAuthMode

logger = logging.getLogger(__name__)

# Gmail OAuth2 endpoints
GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Scopes for API mode (Gmail REST API + Calendar API)
API_MODE_SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

# Scopes for IMAP mode (IMAP/SMTP protocol + Calendar API)
# Compatible with Thunderbird/GNOME OAuth credentials
IMAP_MODE_SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
]


def get_scopes_for_mode(oauth_mode: OAuthMode) -> list[str]:
    if oauth_mode == OAuthMode.API:
        return API_MODE_SCOPES
    else:
        return IMAP_MODE_SCOPES


# Local server details
DEFAULT_CALLBACK_PORT = 8080
DEFAULT_CALLBACK_HOST = "localhost"
CALLBACK_PATH = "/oauth2callback"
SUCCESS_PATH = "/success"

# In-memory token storage
auth_tokens = {
    "access_token": None,
    "refresh_token": None,
    "token_expiry": None,
}


def create_oauth_app() -> Flask:
    """Create the Flask app for OAuth2 callback handling."""
    app = Flask(__name__)

    @app.route(CALLBACK_PATH)
    def oauth2callback():
        # Get authorization code from query parameters
        code = request.args.get("code")
        if not code:
            return "Error: No authorization code received", 400

        # Exchange code for tokens
        client_id = app.config.get("client_id")
        client_secret = app.config.get("client_secret")

        # Make token request
        try:
            import requests

            token_data = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": app.config.get("redirect_uri"),
                "grant_type": "authorization_code",
            }

            response = requests.post(GMAIL_TOKEN_URL, data=token_data)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses

            tokens = response.json()

            # Store tokens in memory
            auth_tokens["access_token"] = tokens.get("access_token")
            auth_tokens["refresh_token"] = tokens.get("refresh_token")
            auth_tokens["token_expiry"] = int(time.time()) + tokens.get(
                "expires_in", 3600
            )

            logger.info("Successfully obtained OAuth2 tokens")

            return redirect(url_for("success"))

        except Exception as e:
            logger.error(f"Error exchanging authorization code: {e}")
            return f"Error: Failed to exchange authorization code: {e}", 500

    @app.route(SUCCESS_PATH)
    def success():
        """Success page shown after successful authentication."""
        return """
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 30px;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                .success {
                    background-color: #d4edda;
                    color: #155724;
                    padding: 15px;
                    border-radius: 4px;
                    margin: 20px 0;
                }
            </style>
        </head>
        <body>
            <h1>Authentication Successful!</h1>
            <div class="success">
                <p>You have successfully authenticated with Gmail.</p>
                <p>You may now close this browser window and return to the application.</p>
            </div>
        </body>
        </html>
        """

    return app


def run_local_server(
    client_id: str,
    client_secret: str,
    oauth_mode: OAuthMode,
    port: int = DEFAULT_CALLBACK_PORT,
    host: str = DEFAULT_CALLBACK_HOST,
    manual_mode: bool = False,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Run a local server to handle the OAuth2 callback.

    Args:
        client_id: OAuth2 client ID
        client_secret: OAuth2 client secret
        port: Port for the local server
        host: Host for the local server
        manual_mode: If True, prompt user to paste redirect URL instead of running server

    Returns:
        Tuple of (access_token, refresh_token, expiry) or (None, None, None) if failed
    """
    redirect_uri = f"http://{host}:{port}{CALLBACK_PATH}"

    state = secrets.token_urlsafe(16)
    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(get_scopes_for_mode(oauth_mode)),
        "access_type": "offline",
        "state": state,
        "prompt": "consent",
    }
    auth_url = f"{GMAIL_AUTH_URL}?{urlencode(auth_params)}"

    if manual_mode:
        return _run_manual_flow(client_id, client_secret, redirect_uri, auth_url)
    else:
        return _run_server_flow(
            client_id, client_secret, redirect_uri, auth_url, port, host
        )


def _run_manual_flow(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    auth_url: str,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Manual OAuth flow where user pastes the redirect URL."""
    import requests

    print("\n" + "=" * 60)
    print("MANUAL AUTHENTICATION MODE")
    print("=" * 60)
    print("\n1. Open this URL in your browser:\n")
    print(auth_url)
    print("\n2. Complete the authentication in your browser.")
    print("\n3. You will be redirected to a URL that may not load.")
    print("   Copy the ENTIRE URL from your browser's address bar.")
    print(
        "   It will look like: http://localhost:8080/oauth2callback?code=...&state=..."
    )
    print("\n" + "-" * 60)

    redirect_response = input("\nPaste the full redirect URL here: ").strip()

    if not redirect_response:
        print("Error: No URL provided.")
        return None, None, None

    try:
        parsed = urlparse(redirect_response)
        query_params = parse_qs(parsed.query)

        code = query_params.get("code", [None])[0]
        if not code:
            print("Error: No authorization code found in URL.")
            print("Make sure you copied the entire URL including the ?code=... part.")
            return None, None, None

        token_data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        response = requests.post(GMAIL_TOKEN_URL, data=token_data)
        response.raise_for_status()

        tokens = response.json()

        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        token_expiry = int(time.time()) + tokens.get("expires_in", 3600)

        print("\n✓ Authentication successful!")
        return access_token, refresh_token, token_expiry

    except Exception as e:
        logger.error(f"Error in manual OAuth flow: {e}")
        print(f"\nError: {e}")
        return None, None, None


def _run_server_flow(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    auth_url: str,
    port: int,
    host: str,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Server-based OAuth flow with local callback server."""
    app = create_oauth_app()

    app.config.update(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    auth_tokens["access_token"] = None
    auth_tokens["refresh_token"] = None
    auth_tokens["token_expiry"] = None

    print(f"\nOpening browser for Gmail authentication...")
    webbrowser.open(auth_url)

    print(f"\nWaiting for authentication at http://{host}:{port}{CALLBACK_PATH}")
    print(
        "\nIf the browser doesn't open or callback fails, restart with --manual flag."
    )

    import threading

    server_should_stop = threading.Event()

    def run_server():
        from werkzeug.serving import make_server

        server = make_server(host, port, app, threaded=True)
        server.timeout = 0.5

        while not server_should_stop.is_set():
            server.handle_request()

    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    try:
        max_wait_time = 5 * 60
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            if auth_tokens["access_token"] is not None:
                break

            time.sleep(1)

        if auth_tokens["access_token"] is None:
            print("\nAuthentication timed out. Please try again.")
            print(
                "Tip: If running in Docker or the callback isn't working, use --manual flag."
            )
            return None, None, None

    finally:
        server_should_stop.set()
        server_thread.join(timeout=5)

    return (
        auth_tokens["access_token"],
        auth_tokens["refresh_token"],
        auth_tokens["token_expiry"],
    )


def load_client_credentials(credentials_file: str) -> Tuple[str, str]:
    """
    Load client credentials from the downloaded JSON file.

    Args:
        credentials_file: Path to the credentials JSON file

    Returns:
        Tuple of (client_id, client_secret)

    Raises:
        FileNotFoundError: If the credentials file doesn't exist
        ValueError: If the credentials file is invalid
    """
    if not credentials_file:
        raise ValueError("No credentials file specified")

    credentials_path = Path(credentials_file)
    if not credentials_path.exists():
        raise FileNotFoundError(f"Credentials file not found: {credentials_file}")

    try:
        with open(credentials_path) as f:
            try:
                credentials = json.load(f)
            except json.JSONDecodeError as e:
                # Convert JSONDecodeError to ValueError for consistent error handling
                raise ValueError(
                    f"Invalid JSON in credentials file: {credentials_file}. Error: {str(e)}"
                )

        if "installed" in credentials:
            client_config = credentials["installed"]
        elif "web" in credentials:
            client_config = credentials["web"]
        else:
            raise ValueError(f"Invalid credentials format in {credentials_file}")

        client_id = client_config.get("client_id")
        client_secret = client_config.get("client_secret")

        if not client_id or not client_secret:
            raise ValueError(
                f"Missing client_id or client_secret in {credentials_file}"
            )

        return client_id, client_secret
    except Exception as e:
        # Catch any other potential errors and convert them to ValueError
        if not isinstance(e, (ValueError, FileNotFoundError)):
            raise ValueError(f"Error reading credentials file: {str(e)}")
        raise


def perform_oauth_flow(
    oauth_mode: OAuthMode,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    credentials_file: Optional[str] = None,
    port: int = DEFAULT_CALLBACK_PORT,
    config_path: Optional[str] = None,
    config_output: Optional[str] = None,
    manual_mode: bool = False,
) -> Dict[str, Any]:
    """Run the OAuth flow to get Gmail access and refresh tokens.

    Args:
        client_id: OAuth2 client ID (optional, will prompt if not provided)
        client_secret: OAuth2 client secret (optional, will prompt if not provided)
        port: Port for the local server
        config_path: Path to existing config file to update (optional)
        config_output: Path to save the updated config file (optional)

    Returns:
        Updated configuration dictionary
    """
    # Try to load credentials from file first if provided
    if credentials_file and not (client_id and client_secret):
        try:
            logger.info(f"Attempting to load credentials from {credentials_file}")
            loaded_client_id, loaded_client_secret = load_client_credentials(
                credentials_file
            )
            client_id = client_id or loaded_client_id
            client_secret = client_secret or loaded_client_secret
            logger.info("Successfully loaded credentials from file")
        except Exception as e:
            logger.warning(f"Failed to load credentials from file: {e}")

    # Use environment variables if not provided
    client_id = client_id or os.environ.get("GMAIL_CLIENT_ID")
    client_secret = client_secret or os.environ.get("GMAIL_CLIENT_SECRET")

    # Prompt for client_id and client_secret if not provided
    if not client_id:
        client_id = input("Enter your Google OAuth2 client ID: ").strip()

    if not client_secret:
        client_secret = input("Enter your Google OAuth2 client secret: ").strip()

    if not client_id or not client_secret:
        print("Error: Client ID and secret are required.")
        sys.exit(1)

    # Run the OAuth flow
    print("Starting OAuth2 authentication flow...")
    access_token, refresh_token, expiry = run_local_server(
        client_id=client_id,
        client_secret=client_secret,
        oauth_mode=oauth_mode,
        port=port,
        manual_mode=manual_mode,
    )

    if not access_token or not refresh_token:
        print("Error: Failed to obtain OAuth2 tokens.")
        sys.exit(1)

    print("Authentication successful!")

    # Build OAuth2 configuration
    oauth2_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "access_token": access_token,
        "token_expiry": expiry,
    }

    # Load existing config - check config_path first, then config_output
    config_data = {}
    config_to_load = config_path or config_output
    if config_to_load:
        config_file = Path(config_to_load)
        if config_file.exists():
            with open(config_file, "r") as f:
                config_data = yaml.safe_load(f) or {}
                logger.info(f"Loaded existing configuration from {config_to_load}")

    # Update config with OAuth2 data
    if "imap" not in config_data:
        config_data["imap"] = {}

    config_data["imap"]["oauth2"] = oauth2_data

    # Save updated config if output path specified
    if config_output:
        output_file = Path(config_output)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)
            logger.info(f"Saved updated configuration to {config_output}")

    print("\nOAuth2 configuration:")
    print(json.dumps(oauth2_data, indent=2, default=str))

    print(
        "\nTo use these credentials, add them to your config.yaml file under the imap.oauth2 key."
    )
    print("Alternatively, you can set the following environment variables:")
    print(f"  GMAIL_CLIENT_ID={client_id}")
    print(f"  GMAIL_CLIENT_SECRET={client_secret}")
    print(f"  GMAIL_REFRESH_TOKEN={refresh_token}")

    return config_data


def main():
    """Run the browser-based OAuth2 setup tool."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Browser-based OAuth2 authentication for Gmail"
    )
    parser.add_argument(
        "--client-id",
        help="Google OAuth2 client ID",
        default=os.environ.get("GMAIL_CLIENT_ID"),
    )
    parser.add_argument(
        "--client-secret",
        help="Google OAuth2 client secret",
        default=os.environ.get("GMAIL_CLIENT_SECRET"),
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port for the local callback server",
        default=DEFAULT_CALLBACK_PORT,
    )
    parser.add_argument(
        "--config",
        help="Path to existing config file to update",
        default=None,
    )
    parser.add_argument(
        "--output",
        help="Path to save the updated config file",
        default="config.yaml",
    )
    parser.add_argument(
        "--mode",
        choices=["api", "imap"],
        required=True,
        help="OAuth mode: 'api' for Gmail REST API or 'imap' for IMAP/SMTP (Thunderbird credentials)",
    )

    parser.add_argument(
        "--manual",
        action="store_true",
        help="Use manual mode: paste redirect URL instead of running local server (useful in Docker)",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    oauth_mode = OAuthMode.from_string(args.mode)

    perform_oauth_flow(
        oauth_mode=oauth_mode,
        client_id=args.client_id,
        client_secret=args.client_secret,
        port=args.port,
        config_path=args.config,
        config_output=args.output,
        manual_mode=args.manual,
    )


if __name__ == "__main__":
    main()
