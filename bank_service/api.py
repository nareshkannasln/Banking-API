# -------------------- api.py -------------------- #
import json
import base64
import frappe
from frappe.utils import validate_email_address
from bank_service.utils import (
    generate_account_number,
    validate_phone,
    generate_bank_keypair,
    get_public_key_pem_pkcs8,
    encrypt_with_client_key,
)

from frappe.utils import now
from bank_service.utils import (
    decrypt_with_bank_key,
    encrypt_with_client_key,
)



@frappe.whitelist(allow_guest=True)
def create_bank_account():
    try:
        # ---------------- Parse request ----------------
        raw_data = frappe.request.data or b""
        print("Raw request data:", raw_data)

        try:
            data = json.loads(raw_data.decode("utf-8"))
        except Exception as e:
            return {"status": "fail", "message": f"Invalid JSON: {e}"}

        print("Parsed JSON data:", data)

        # ---------------- Extract inputs ----------------
        account_name = (data.get("account_name") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip()
        address = (data.get("address") or "").strip()
        account_type = (data.get("account_type") or "").strip()
        client_public_key = (data.get("client_public_key") or data.get("client_public_key_file") or "").strip()

        print("Inputs extracted:", {
            "account_name": account_name,
            "phone": phone,
            "email": email,
            "address": address,
            "account_type": account_type,
            "client_public_key": client_public_key[:30] + "..." if client_public_key else ""
        })

        # ---------------- Validations ----------------
        print("Validating inputs...")
        if not account_name:
            return {"status": "fail", "message": "Account name required"}
        validate_phone(phone)
        if email:
            validate_email_address(email, throw=True)
        if account_type not in ("Savings", "Current"):
            return {"status": "fail", "message": "Invalid account type"}
        if not client_public_key.startswith("-----BEGIN"):
            return {"status": "fail", "message": "client_public_key must be PEM format"}

        # ---------------- Generate bank keypair ----------------
        print("Generating bank keypair...")
        bank_pub, bank_priv = generate_bank_keypair("HDFC")
        bank_pub_pem = get_public_key_pem_pkcs8(bank_pub)
        print("Bank public key generated.")
        print(bank_pub_pem)
        if client_public_key == bank_pub_pem:
            frappe.throw("Client public key cannot be the same as bank public key")

        account_no = generate_account_number()
        while frappe.db.exists("HDFC Customer", {"account_number": account_no}):
            account_no = generate_account_number()
        print("Generated account number:", account_no)



        print("Creating HDFC Customer record...")
        bank_acc = frappe.new_doc("HDFC Customer")
        bank_acc.update({
            "account_name": account_name,
            "account_number": account_no,
            "account_type": account_type,
            "phone": phone,
            "email": email,
            "address": address,
            "client_public_key": client_public_key,  
        })
        bank_acc.insert(ignore_permissions=True)
        print("HDFC Customer inserted:", account_no)

        print("Creating ERPNext Bank Account...")
        erp_bank_acc = frappe.new_doc("Bank Account")
        erp_bank_acc.update({
            "account_name": account_name,
            "bank": "HDFC",
            "account_type": account_type,
            "bank_account_no": account_no,
        })
        erp_bank_acc.insert(ignore_permissions=True)
        bank_acc.db_set("erpnext_bank_account", erp_bank_acc.name)
        print("ERPNext Bank Account inserted:", erp_bank_acc.name)

        response_payload = {
            "account_number": account_no,
            "account_name": account_name,
            "account_type": account_type,
            "erpnext_bank_account": erp_bank_acc.name,
            "bank_public_key": bank_pub_pem,
        }
        print("Response payload prepared:", {k: v if k != "bank_public_key" else "PEM..." for k, v in response_payload.items()})

        encrypted_response = encrypt_with_client_key(client_public_key, response_payload)
        print("Response encrypted successfully.")
        print("Client public key:", client_public_key[:100])
        print("Bank public key:", bank_pub_pem[:100])

        return {"status": "success", "encrypted_response": encrypted_response}
    
        


    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Bank Account Error")
        print("Exception occurred:", str(e))
        return {"status": "error", "message": str(e)}






@frappe.whitelist(allow_guest=True)
def make_transaction():
    try:
        raw_data = frappe.request.data or b""
        data = json.loads(raw_data.decode("utf-8"))
        encrypted_payload = data.get("encrypted_payload")
        client_public_key = (data.get("client_public_key") or "").strip()

        if not encrypted_payload or not client_public_key:
            return {"status": "fail", "message": "Missing encrypted_payload or client_public_key"}

        payload = decrypt_with_bank_key(encrypted_payload)
        print("Decrypted transaction payload:", payload)

        transaction_type = payload.get("transaction_type")
        from_account = payload.get("from_account")
        to_account = payload.get("to_account")
        amount = payload.get("amount")
        remarks = payload.get("remarks", "")

        if transaction_type not in ("Deposit", "Account Transfer"):
            return {"status": "fail", "message": "Invalid transaction type"}
        if transaction_type == "Deposit" and not to_account:
            return {"status": "fail", "message": "Deposit requires to_account"}
        if transaction_type == "Account Transfer" and (not from_account or not to_account):
            return {"status": "fail", "message": "Account Transfer requires both from_account and to_account"}

        if transaction_type == "Deposit":
            from_account = "Cash In Hand" 

        trx = frappe.new_doc("Transactions")
        trx.update({
            "transaction_type": transaction_type,
            "from_account": from_account,
            "to_account": to_account,
            "amount": amount,
            "status": "Initiated",
            "date_time": now(),
        })
        trx.insert(ignore_permissions=True)
        trx_id = trx.name

        je = frappe.new_doc("Journal Entry")
        je.update({
            "voucher_type": "Bank Entry",
            "posting_date": now(),
            "user_remark": remarks,
            "accounts": [
                {"account": from_account, "credit_in_account_currency": amount},
                {"account": to_account, "debit_in_account_currency": amount},
            ],
        })
        je.insert(ignore_permissions=True)
        je.submit()

        trx.db_set("status", "Completed")

        response_payload = {
            "transaction_id": trx_id,
            "transaction_type": transaction_type,
            "from_account": from_account,
            "to_account": to_account,
            "amount": amount,
            "status": "Completed",
            "journal_entry": je.name,
            "timestamp": now(),
        }

        encrypted_response = encrypt_with_client_key(client_public_key, response_payload)

        return {"status": "success", "encrypted_response": encrypted_response}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Transaction API Error")
        return {"status": "error", "message": str(e)}
