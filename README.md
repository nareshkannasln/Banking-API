Bank Service App

This is a Frappe application that provides banking-related APIs such as account creation and transactions.
It is designed to integrate with ERPNext or other Frappe-based systems.

Installation

Navigate to your frappe-bench directory.

Get the app:

bench get-app bank_service <repo_url>


Install the app on your site:

bench --site <your-site> install-app bank_service


Restart the server:

bench start

API Endpoints
1. Create Bank Account

URL

POST /api/method/bank_service.api.create_bank_account


Request Body

{
  "account_name": "John Doe",
  "phone": "9876543210",
  "address": "Chennai",
  "email": "john@example.com",
  "account_type": "Savings",
  "client_public_key": "-----BEGIN PUBLIC KEY-----...-----END PUBLIC KEY-----"
}


Response

{
  "status": "success",
  "account_number": "12345678901",
  "account_name": "John Doe",
  "account_type": "Savings",
  "erpnext_bank_account": "John Doe - HDFC",
  "bank_public_key": "-----BEGIN PUBLIC KEY-----...-----END PUBLIC KEY-----"
}

2. Make Transaction

URL

POST /api/method/bank_service.api.make_transaction


Request Body

{
  "from_account": "12345678901",
  "to_account": "98765432109",
  "amount": 500.0,
  "transaction_type": "debit",
  "client_public_key": "-----BEGIN PUBLIC KEY-----...-----END PUBLIC KEY-----"
}


Response

{
  "status": "success",
  "transaction_id": "TXN123456",
  "message": "Transaction completed"
}

Notes

All sensitive response data is encrypted with the client’s public key.

The server generates its own RSA keypair for encryption and decryption.

Keys are stored under the site’s private/bank_keys folder.

Development

Requires Frappe framework version 14 or higher.

Python dependencies:

cryptography

rsa
