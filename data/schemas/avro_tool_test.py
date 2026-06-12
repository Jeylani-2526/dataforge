import json
import sys
from io import BytesIO
from fastavro import parse_schema, schemaless_writer, schemaless_reader


def main():

    # Check that exactly two command-line arguments are provided:
    # 1. Avro schema file (.avsc)
    # 2. JSON record file
    if len(sys.argv) != 3:
        print("Usage: python schemas/validate_schema.py <schema.avsc> <record.json>")
        sys.exit(1)

    # Store file paths from command-line arguments
    schema_path = sys.argv[1]
    record_path = sys.argv[2]

    try:

        # Load the Avro schema from the specified .avsc file
        with open(schema_path, "r", encoding="utf-8") as schema_file:
            schema = json.load(schema_file)

        # Load the JSON test record
        with open(record_path, "r", encoding="utf-8") as record_file:
            record = json.load(record_file)

        # Parse the schema so fastavro can use it
        parsed_schema = parse_schema(schema)

        # Create an in-memory binary buffer
        buffer = BytesIO()

        # Serialize the JSON record into Avro binary format
        schemaless_writer(buffer, parsed_schema, record)

        # Move the buffer pointer back to the beginning
        # so the serialized data can be read again
        buffer.seek(0)

        # Deserialize the Avro binary data back into a Python object
        decoded_record = schemaless_reader(buffer, parsed_schema)

        # Display original and decoded records
        print("Original record:", record)
        print("Decoded record:", decoded_record)

        # Verify round-trip integrity
        # PASS if the decoded record matches the original record
        if record == decoded_record:
            print("PASS - Round trip successful")
            sys.exit(0)
        else:
            print("FAIL - Data mismatch")
            sys.exit(1)

    # Catch and report any unexpected errors
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


# Program entry point
if __name__ == "__main__":
    main()