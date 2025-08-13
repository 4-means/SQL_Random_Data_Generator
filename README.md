# SQL_Random_Data_Generator
A tool for populating your SQL databases with randomized data, making it perfect for development, unit testing, and stress testing. It handles table relationships to create a complete and functional dataset.

## Features
This program streamlines the process of generating test data for your development and testing environments.

* **Schema-Driven Generation:** Reads your SQL schemas to understand table structures, data types, and field lengths.

* **Data Creation:*** Automatically generates random data for each field that respects the defined data type (INT, VARCHAR, DATE, etc.) and length constraints.

* **Key-Aware Data Generation:** Understands and respects primary keys and foreign keys to create valid relationships between tables, ensuring referential integrity. This is crucial for creating realistic datasets that can be used for table joins.

* **Dual Output Formats:** Provides the generated data in two useful formats:

  * **SQL INSERT Statements:** Ready-to-execute SQL statements to quickly populate your database.

  * **JSON:** A clean, structured JSON file of the data, to use in other applications or APIs, or to validate data.  

* **Customizable:** Easily configure the number of rows to generate for each table, giving you full control over the dataset size.
