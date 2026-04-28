import os

# regular expression module for splitting records based on device type(HOST, SWITCH, ROUTER)
# basically matching the device type followed by a comma, and splitting the text at those points,
# while keeping the device type in the resulting list
import re


def read_file(file_path):
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.path.dirname(__file__), file_path)

    try:
        with open(file_path, "r") as file:
            # combine every line into a single string, while stripping leading and trailing whitespace, and ignoring empty lines
            raw_text = " ".join(line.strip() for line in file if line.strip())

        # raw_text is a single string containing all the data from the file,
        # we can now split it into records based on device type

        # \s+ split raw_text at one or more spaces
        # (?=(?:HOST|SWITCH|ROUTER),) is a positive lookahead that checks for the presence of "HOST," "SWITCH," or "ROUTER,"
        # without including it in the split results, ensuring that each record starts with the device type
        records = re.split(r"\s+(?=(?:HOST|SWITCH|ROUTER),)", raw_text)

        data_info = []

        for record in records:
            fields = [field.strip().replace(" ", "") for field in record.split(",")]
            data_info.append(fields)

        return data_info
    except FileNotFoundError as e:
        print(f"The file {file_path} does not exist, error: {e}")
        return []
