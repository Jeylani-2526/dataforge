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

        # Load the JSON data that will be validated.
        #
        # The validator supports both:
        # 1. A single JSON object
        # 2. A JSON array containing multiple records
        with open(record_path, "r", encoding="utf-8") as record_file:
            input_data = json.load(record_file)

        # Parse the schema into a format fastavro can use
        parsed_schema = parse_schema(schema)

        # Convert a single JSON object into a one-item list.
        #
        # This allows the same validation loop to be used for both
        # single-record files and files containing multiple records.
        if isinstance(input_data, dict):
            records = [input_data]

        elif isinstance(input_data, list):
            records = input_data

        else:
            print("ERROR: JSON input must be an object or an array of objects")
            sys.exit(1)

        # Validate that the input file contains at least one record
        if len(records) == 0:
            print("ERROR: No records found in the JSON input file")
            sys.exit(1)

        # Counters used to create a validation summary
        passed_records = 0
        failed_records = 0

        # Validate every record independently.
        #
        # Each record is serialized into Avro binary format and
        # immediately deserialized again.
        #
        # This verifies that the record conforms to the schema
        # and that no information is lost during the round-trip.
        for index, record in enumerate(records, start=1):

            # Verify that every item in the JSON array is an object
            if not isinstance(record, dict):
                print(f"FAIL: Record {index} is not a JSON object")
                failed_records += 1
                continue

            # Remove helper fields that are not part of the Avro schema.
            #
            # The test files may contain a "_comment" field used only
            # to describe the purpose of each test record.
            clean_record = {
                key: value
                for key, value in record.items()
                if key != "_comment"
            }

            try:

                # Create an in-memory binary buffer to store
                # the serialized Avro data
                buffer = BytesIO()

                # Serialize the JSON record into Avro binary format
                # using the provided schema
                schemaless_writer(buffer, parsed_schema, clean_record)

                # Reset the buffer position to the beginning
                # so the serialized data can be read back
                buffer.seek(0)

                # Deserialize the Avro binary data back into
                # a Python dictionary/object
                decoded_record = schemaless_reader(buffer, parsed_schema)

                # Read the sensor type for clearer validation output
                sensor_type = clean_record.get("sensor_type", "UNKNOWN")

                # Print both records for visibility and debugging
                print(f"\nRecord {index} ({sensor_type})")
                print("Original record:", clean_record)
                print("Decoded record:", decoded_record)

                # Verify round-trip integrity:
                # The deserialized record must match the original record
                if clean_record == decoded_record:
                    print(f"PASS: Record {index} round-trip validation successful")
                    passed_records += 1

                else:
                    print(f"FAIL: Record {index} round-trip validation failed")
                    failed_records += 1

            # Catch validation errors for the current record.
            #
            # Processing continues so that all records are checked,
            # even if one record fails.
            except Exception as error:
                sensor_type = clean_record.get("sensor_type", "UNKNOWN")
                print(f"\nFAIL: Record {index} ({sensor_type})")
                print(f"ERROR: {error}")
                failed_records += 1

        # Print a compiled validation summary after all records
        # have been processed
        print("\nValidation summary")
        print("------------------")
        print(f"Total records: {len(records)}")
        print(f"Passed records: {passed_records}")
        print(f"Failed records: {failed_records}")

        # Return a successful exit code only when every record
        # has passed the validation
        if failed_records == 0:
            print("PASS: All records passed round-trip validation")
            sys.exit(0)

        # At least one record failed validation
        print("FAIL: One or more records failed validation")
        sys.exit(1)

    # Catch and report a missing schema or record file
    except FileNotFoundError as error:
        print(f"ERROR: File not found: {error.filename}")
        sys.exit(1)

    # Catch and report invalid JSON syntax
    except json.JSONDecodeError as error:
        print(
            f"ERROR: Invalid JSON at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        )
        sys.exit(1)

    # Catch and report any other unexpected errors
    # such as an invalid Avro schema
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)


# Application entry point
if __name__ == "__main__":
    main()
