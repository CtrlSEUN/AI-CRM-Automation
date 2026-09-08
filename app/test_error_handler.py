from error_handler import handle_error


print("===== ERROR HANDLER TEST =====")

try:

    number = int("abc")

except ValueError as error:

    handle_error(
        error,
        "Testing invalid number conversion"
    )