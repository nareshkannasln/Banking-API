import frappe
from frappe import _

@frappe.whitelist(allow_guest=False)
def create_bank_account(account_name, phone=None, address=None, account_number=None):
    """
    Create a Bank Account record in bank_service app.
    """
    try:
        if not account_name:
            return {"status": "fail", "message": _("Account Name is required.")}

        if not account_number:
            return {"status": "fail", "message": _("Account Number is required.")}

        if frappe.db.exists("Bank Account", {"account_number": account_number}):
            return {"status": "fail", "message": _("Account Number already exists.")}

        bank_account = frappe.new_doc("Bank Account")
        bank_account.account_name = account_name
        bank_account.phone = phone
        bank_account.address = address
        bank_account.account_number = account_number
        bank_account.insert(ignore_permissions=True)

        return {
            "status": "success",
            "message": _("Bank Account created successfully."),
            "bank_account_id": bank_account.name
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Bank Account API Error")
        return {"status": "error", "message": _("Something went wrong. Please try again.")}
