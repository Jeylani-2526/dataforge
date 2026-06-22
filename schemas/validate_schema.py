import json
import sys
from io import BytesIO

# fastavro functions used for schema parsing,
# serialization and deserialization
from fastavro import parse_schema, schemaless_reader, schemaless_writer


def main():

    # Validate that exactly two command-line arguments are provided:
    # 1. Path to the Avro schema file (.avsc)
    # 2. Path to the JSON test record file
    #
    # Example:
    # python schemas/validate_schema.py schema.avsc record.json
    #
    # sys.argv always contains the script name as the first element,
    # therefore we expect a total length of 3:
    # [script_name, schema_file, record_file]
    #
    # If the required arguments are missing or too many arguments are
    # provided, display the correct usage and terminate the program.
    if len(sys.argv) != 3:
        print("Usage: python schemas/validate_schema.py <schema.avsc> <record.json>")
        sys.exit(1)

    # Store command-line arguments
    schema_path = sys.argv[1]
    record_path = sys.argv[2]

    try:

        # Load the Avro schema from the specified file
        with open(schema_path, "r", encoding="utf-8") as schema_file:
            schema = json.load(schema_file)

        # Load the JSON test record that will be validated
        with open(record_path, "r", encoding="utf-8") as record_file:
            record = json.load(record_file)

        # Parse the schema into a format fastavro can use
        parsed_schema = parse_schema(schema)

        # Create an in-memory binary buffer to store
        # the serialized Avro data
        buffer = BytesIO()

        # Serialize the JSON record into Avro binary format
        # using the provided schema
        schemaless_writer(buffer, parsed_schema, record)

        # Reset the buffer position to the beginning
        # so the serialized data can be read back
        buffer.seek(0)

        # Deserialize the Avro binary data back into
        # a Python dictionary/object
        decoded_record = schemaless_reader(buffer, parsed_schema)

        # Print both records for visibility and debugging
        print("Original record:", record)
        print("Decoded record:", decoded_record)

        # Verify round-trip integrity:
        # The deserialized record must match the original record
        if record == decoded_record:
            print("PASS: Round-trip validation successful")
            sys.exit(0)

        # Records differ after serialization/deserialization
        print("FAIL: Round-trip validation failed")
        sys.exit(1)

    # Catch and report any unexpected errors
    # such as invalid schema, invalid JSON, missing files, etc.
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)


# Application entry point
if __name__ == "__main__":
    main()