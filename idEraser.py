import csv

def remove_first_column(input_file, output_file):
    with open(input_file, mode='r', newline='', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        rows = [row[1:] for row in reader]  # Удаление первого столбца

    with open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(rows)

if __name__ == "__main__":
    input_csv_file = 'temperatures.csv'   # Замените на путь к вашему исходному CSV файлу
    output_csv_file = 'temperaturesNOID.csv' # Замените на путь к выходному CSV файлу
    remove_first_column(input_csv_file, output_csv_file)
    print(f"First column removed and saved to {output_csv_file}")
