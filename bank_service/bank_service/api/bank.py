import frappe, random

def generate_account_number():
    length = random.choice([11, 12])
    return str(random.randint(10**(length-1), 10**length - 1))

@frappe.whitelist()
def create_account(customer, account_type="Savings"):
    try:
        if not frappe.db.exists("Customer", customer):
            return {"status": "fail", "message": "Invalid customer"}

        account_no = generate_account_number()

        # 1. Create Bank Account (HDFC Customer)
        bank_acc = frappe.new_doc("HDFC Customer")
        bank_acc.account_number = account_no
        bank_acc.account_name = frappe.db.get_value("Customer", customer, "customer_name")
        bank_acc.account_type = account_type
        bank_acc.balance = 0
        bank_acc.status = "Active"
        bank_acc.insert(ignore_permissions=True)

        # 2. Map to ERPNext Customer (Customer Accounts)
        cust_acc = frappe.new_doc("Customer Accounts")
        cust_acc.customer = customer
        cust_acc.bank_account = bank_acc.name
        cust_acc.status = "Active"
        cust_acc.insert(ignore_permissions=True)

        return {
            "status": "success",
            "account_number": account_no,
            "customer": customer,
            "account_type": account_type
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Account Error")
        return {"status": "error", "message": "Something went wrong"}







@frappe.whitelist()
def create_transaction(from_account=None, to_account=None, amount=0, reference_no=None, vid=None):
    try:
        amount = float(amount)

        if not to_account:
            return {"status": "fail", "message": "To Account required"}

        # Case 1: Deposit (only to_account given)
        if not from_account:
            from_account = "BANK_CASH_ACCOUNT"

        # Fetch accounts
        from_acc = frappe.get_doc("HDFC Customer", {"account_number": from_account})
        to_acc = frappe.get_doc("HDFC Customer", {"account_number": to_account})

        if from_acc.account_number != "BANK_CASH_ACCOUNT" and from_acc.balance < amount:
            return {"status": "fail", "message": "Insufficient balance"}

        # Update balances
        if from_acc.account_number != "BANK_CASH_ACCOUNT":
            from_acc.balance -= amount
            from_acc.save(ignore_permissions=True)

        to_acc.balance += amount
        to_acc.save(ignore_permissions=True)

        # Record transaction
        tx = frappe.new_doc("Transactions")
        tx.from_account = from_account
        tx.to_account = to_account
        tx.amount = amount
        tx.reference_no = reference_no
        tx.vid = vid
        tx.status = "Success"
        tx.insert(ignore_permissions=True)

        return {"status": "success", "transaction_id": tx.name}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Transaction Error")
        return {"status": "error", "message": "Something went wrong"}
