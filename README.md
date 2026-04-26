# Stockify

# to update any row use this code 

# from django.db import connection
# with connection.cursor() as cursor:
#     cursor.execute(
#         "UPDATE your_table SET your_column = %s WHERE id = %s",
#         ["new_value", 1]
#     )