# SQL_Random_Data_Generator
A tool for populating your SQL databases with randomized data, making it perfect for development, unit testing, and stress testing. It handles table relationships to create a complete and functional dataset. The tool does use [Faker](https://github.com/joke2k/faker) in some cases for data generation. 

## Features
This program streamlines the process of generating test data for your development and testing environments.

* **Schema-Driven Generation:** Reads your SQL schemas to understand table structures, data types, and field lengths.

* **Data Creation:*** Automatically generates random data for each field that respects the defined data type (INT, VARCHAR, DATE, etc.) and length constraints.

* **Key-Aware Data Generation:** Understands and respects primary keys and foreign keys to create valid relationships between tables, ensuring referential integrity. This is crucial for creating realistic datasets that can be used for table joins.

* **Dual Output Formats:** Provides the generated data in two useful formats:

  * **SQL INSERT Statements:** Ready-to-execute SQL statements to quickly populate your database.

  * **JSON:** A clean, structured JSON file of the data, to use in other applications or APIs, or to validate data.  

* **Customizable:** Easily configure the number of rows to generate for each table, giving you full control over the dataset size.

## Parameters
* **--schmea-dir**  - The directory that contains the SQL schemas.  Do not pass, or use . for working directory
* **--key-fields**  - The fields used for keys. This will define the parent table and separate multiple fields by a comma. (e.g. par_key1, par_key2). The program uses the fields ot derive the parent table.
* **--num-rows**    - Defines the number of unique rows to create in the parent table.
* **--multipliers** - Defines the number of rows to create in the children tables for each row in the parent table. (e.g., Child_Table_1 = 2, Child_Table_2 = 3)
* **--foreign-map** - Defines the foreign keys that will be used to join the tables.  (e.g. ct1_key1=par_key1,ct1_key2=par_key2,ct2_key1=par_key1,ct2_key2=par_key2)
* **--output-dir**  - The directory where the output files will be created.  Do not pass, or use . for the working directory.

Example command to create fully random data with SQL Schemas in the working directory and output being created in the working directory.
```
python3 generate_random_inserts.py
```



