"""
Google Ads Service

Wrapper for Google Ads API operations:
- Initialize client with credentials
- Fetch customer info
- Fetch campaigns
- Fetch metrics
"""

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import tempfile
import yaml


class GoogleAdsService:
    """Service for interacting with Google Ads API"""
    
    @staticmethod
    def create_client(
        developer_token: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        login_customer_id: Optional[str] = None
    ) -> GoogleAdsClient:
        """
        Create a Google Ads API client.
        
        Args:
            developer_token: Your developer token
            client_id: OAuth client ID
            client_secret: OAuth client secret
            refresh_token: OAuth refresh token
            login_customer_id: Optional login customer ID
            
        Returns:
            GoogleAdsClient instance
        """
        # Create credentials dict
        credentials = {
            "developer_token": developer_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "use_proto_plus": True
        }
        
        if login_customer_id:
            credentials["login_customer_id"] = login_customer_id
        
        # Write to temporary yaml file (GoogleAdsClient expects file)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(credentials, f)
            config_file = f.name
        
        # Create client
        client = GoogleAdsClient.load_from_dict(credentials)
        
        return client
    
    @staticmethod
    def get_customer_info(
        client: GoogleAdsClient,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Get customer account information.
        
        Args:
            client: GoogleAdsClient instance
            customer_id: Customer ID (without hyphens)
            
        Returns:
            Dict with customer info (id, name, currency, timezone)
            
        Raises:
            GoogleAdsException: If API call fails
        """
        ga_service = client.get_service("GoogleAdsService")
        
        query = """
            SELECT 
                customer.id,
                customer.descriptive_name,
                customer.currency_code,
                customer.time_zone
            FROM customer
            LIMIT 1
        """
        
        try:
            response = ga_service.search(customer_id=customer_id, query=query)
            
            for row in response:
                return {
                    "account_id": str(row.customer.id),
                    "account_name": row.customer.descriptive_name or "Unnamed Account",
                    "currency": row.customer.currency_code,
                    "timezone": row.customer.time_zone
                }
            
            # If no results, return basic info
            return {
                "account_id": customer_id,
                "account_name": "Google Ads Account",
                "currency": "USD",
                "timezone": "UTC"
            }
            
        except Exception as ex:
            error_str = str(ex)
            
            if "CUSTOMER_NOT_FOUND" in error_str:
                raise Exception("Customer account not found. Verify Customer ID is correct.")
            elif "UNAUTHENTICATED" in error_str:
                raise Exception("Authentication failed. Reconnect your Google Ads account.")
            else:
                raise Exception(f"Could not fetch customer info: {error_str[:150]}...")
    
    @staticmethod
    def fetch_campaigns(
        client: GoogleAdsClient,
        customer_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch all campaigns for a customer.
        
        Args:
            client: GoogleAdsClient instance
            customer_id: Customer ID (without hyphens)
            
        Returns:
            List of campaign dicts
        """
        ga_service = client.get_service("GoogleAdsService")
        
        query = """
            SELECT 
                campaign.id,
                campaign.name,
                campaign.status
            FROM campaign
            ORDER BY campaign.name
        """
        
        campaigns = []
        
        try:
            response = ga_service.search(customer_id=customer_id, query=query)
            
            for row in response:
                campaign_data = {
                    "platform_campaign_id": str(row.campaign.id),
                    "name": row.campaign.name,
                    "status": row.campaign.status.name.lower(),
                }
                
                campaigns.append(campaign_data)
            
            return campaigns
            
        except Exception as e:
            # Parse Google Ads errors into user-friendly messages
            error_str = str(e)
            
            # Check for common error patterns
            if "CUSTOMER_NOT_FOUND" in error_str:
                raise Exception("Customer account not found. Please verify your Google Ads Customer ID is correct.")
            elif "UNAUTHENTICATED" in error_str:
                raise Exception("Authentication failed. Your Google Ads access token may have expired. Try reconnecting your account.")
            elif "REQUESTED_METRICS_FOR_MANAGER" in error_str:
                raise Exception("Cannot fetch data from Manager Account (MCC). Please use a client account ID instead.")
            elif "UNRECOGNIZED_FIELD" in error_str:
                # Extract the field names if possible
                raise Exception("Invalid query fields. The Google Ads API doesn't recognize some requested fields.")
            elif "PERMISSION_DENIED" in error_str:
                raise Exception("Permission denied. Make sure your Google Ads account has the necessary permissions.")
            elif "INVALID_CUSTOMER_ID" in error_str:
                raise Exception("Invalid Customer ID format. Customer ID should be 10 digits without hyphens.")
            else:
                # For unknown errors, show a simplified message
                # Extract just the main error message if possible
                if "message:" in error_str:
                    try:
                        msg_start = error_str.find('message: "') + 10
                        msg_end = error_str.find('"', msg_start)
                        clean_msg = error_str[msg_start:msg_end]
                        raise Exception(f"Google Ads API Error: {clean_msg}")
                    except:
                        pass
                
                # Last resort: show first 200 chars
                raise Exception(f"Google Ads API Error: {error_str[:200]}...")
    
    @staticmethod
    def fetch_campaign_metrics(
        client: GoogleAdsClient,
        customer_id: str,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """
        Fetch campaign metrics for a date range.
        
        Args:
            client: GoogleAdsClient instance
            customer_id: Customer ID
            start_date: Start date
            end_date: End date
            
        Returns:
            List of metric dicts
        """
        ga_service = client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT 
                campaign.id,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value,
                segments.date
            FROM campaign
            WHERE segments.date >= '{start_date.strftime('%Y-%m-%d')}'
              AND segments.date <= '{end_date.strftime('%Y-%m-%d')}'
              AND campaign.status = 'ENABLED'
            ORDER BY segments.date DESC
        """
        
        metrics = []
        
        try:
            response = ga_service.search(customer_id=customer_id, query=query)
            
            for row in response:
                metric_data = {
                    "platform_campaign_id": str(row.campaign.id),
                    "date": datetime.strptime(row.segments.date, "%Y-%m-%d").date(),
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "cost": row.metrics.cost_micros / 1_000_000,  # Convert micros to currency
                    "conversions": int(row.metrics.conversions),
                    "revenue": row.metrics.conversions_value if row.metrics.conversions_value else None
                }
                
                metrics.append(metric_data)
            
            return metrics
            
        except Exception as e:
            error_str = str(e)
            
            if "CUSTOMER_NOT_FOUND" in error_str:
                raise Exception("Customer account not found. Please verify your Google Ads Customer ID.")
            elif "UNAUTHENTICATED" in error_str:
                raise Exception("Authentication failed. Try reconnecting your Google Ads account.")
            elif "REQUESTED_METRICS_FOR_MANAGER" in error_str:
                raise Exception("Cannot fetch metrics from Manager Account. Use a client account ID.")
            elif "PERMISSION_DENIED" in error_str:
                raise Exception("Permission denied. Check your account permissions.")
            else:
                # Extract clean error message
                if "message:" in error_str:
                    try:
                        msg_start = error_str.find('message: "') + 10
                        msg_end = error_str.find('"', msg_start)
                        clean_msg = error_str[msg_start:msg_end]
                        raise Exception(f"Metrics Error: {clean_msg}")
                    except:
                        pass
                raise Exception(f"Failed to fetch metrics: {error_str[:200]}...")
    
    @staticmethod
    def test_connection(
        client: GoogleAdsClient,
        customer_id: str
    ) -> bool:
        """
        Test if connection works by making a simple API call.
        
        Args:
            client: GoogleAdsClient instance
            customer_id: Customer ID
            
        Returns:
            True if connection works, False otherwise
        """
        try:
            GoogleAdsService.get_customer_info(client, customer_id)
            return True
        except Exception:
            return False