import frappe
from frappe import _
import random


def generate_account_number():
    l = random.choice([11, 12])  
    if l == 11:
        return str(random.randint(10**10, 10**11 - 1))  
    else:
        return str(random.randint(10**11, 10**12 - 1))  



@frappe.whitelist(allow_guest=True)
def create_hdfc_customer(account_name, phone, address):
    account_number = generate_account_number()
    while frappe.db.exists("HDFC Customer", account_number):
        account_number = generate_account_number()

    try:
        doc = frappe.get_doc({
            "doctype": "HDFC Customer",
            "account_name": account_name,
            "phone": phone,
            "address": address,
            "account_number": account_number
        })
        doc.insert(ignore_permissions=True)

        frappe.get_doc({
            "doctype": "Customer Accounts",
            "bank_account_no": account_number,
            "account_name": account_name,
            "bank_name": "HDFC",
            "balance": 0
        }).insert(ignore_permissions=True)

        return {
            "status": "success",
            "message": _("Account created successfully."),
            "account_number": account_number
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create HDFC Customer Error")
        return {"status": "fail", "message": str(e)}


@frappe.whitelist()
def make_transaction(from_account=None, to_account=None, transaction_type=None, amount=0):
    try:
        amount = float(amount)
        if amount <= 0:
            return {"status": "fail", "message": _("Amount must be greater than zero.")}

        if transaction_type not in ["Deposit", "Account Transfer"]:
            return {"status": "fail", "message": _("Invalid transaction type.")}

        if transaction_type == "Deposit":
            if not to_account:
                return {"status": "fail", "message": _("'to_account' is required for deposit.")}

            acc = frappe.get_doc("Customer Accounts", {"bank_account_no": to_account})
            acc.balance += amount
            acc.save(ignore_permissions=True)

        elif transaction_type == "Account Transfer":
            if not from_account or not to_account:
                return {"status": "fail", "message": _("Both 'from_account' and 'to_account' are required for transfer.")}

            from_acc = frappe.get_doc("Customer Accounts", {"bank_account_no": from_account})
            to_acc = frappe.get_doc("Customer Accounts", {"bank_account_no": to_account})

            if from_acc.balance < amount:
                return {"status": "fail", "message": _("Insufficient balance.")}

            from_acc.balance -= amount
            to_acc.balance += amount
            from_acc.save(ignore_permissions=True)
            to_acc.save(ignore_permissions=True)

        # Log transaction
        frappe.get_doc({
            "doctype": "Transactions",
            "from_account": from_account if from_account else "",
            "to_account": to_account if to_account else "",
            "transaction_type": transaction_type,
            "amount": amount,
            "date": frappe.utils.nowdate()
        }).insert(ignore_permissions=True)

        return {"status": "success", "message": _("Transaction completed successfully.")}

    except frappe.DoesNotExistError:
        return {"status": "fail", "message": _("Account not found.")}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Make Transaction Error")
        return {"status": "fail", "message": str(e)}


@frappe.whitelist()
def get_balance(account_number):
    try:
        balance = frappe.db.get_value("Customer Accounts", {"bank_account_no": account_number}, "balance")
        if balance is None:
            return {"status": "fail", "message": _("Account not found.")}

        return {
            "status": "success",
            "message": _("Balance fetched successfully."),
            "data": {"account_number": account_number, "balance": balance}
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Balance Error")
        return {"status": "fail", "message": str(e)}
