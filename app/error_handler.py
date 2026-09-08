def handle_error(error, context=""):
    """
    Handle and display application errors safely.
    """

    print("\n===== ERROR =====")

    if context:
        print(f"Operation: {context}")

    print(f"Error: {error}")
    print("The CRM was unable to complete this operation.")

    print("=================")