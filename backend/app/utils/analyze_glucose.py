from typing import Tuple, Union
import pandas as pd
import numpy as np  # 用于处理 NaN (Not a Number)
import pathlib
import argparse
import sys
import logging

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def calculate_glucose_stats(filepath: pathlib.Path) -> Tuple[str, Union[float, str], Union[float, str], int]:
    """
    Calculates mean and standard deviation for the 'glucose' column of a CSV file.

    Args:
        filepath: Path object for the CSV file.

    Returns:
        A tuple: (filename, mean_glucose, std_dev_glucose, valid_readings_count).
        Returns 'N/A' or error strings if calculation fails or no valid data.
    """
    filename = filepath.name
    logger.info(f'Processing {filename}...')
    try:
        # Read CSV
        # 'errors='coerce'' in pd.to_numeric will turn values that cannot be converted to numeric into NaN
        # We read as string initially to ensure -1 is treated as a string before conversion
        df = pd.read_csv(filepath, dtype=str)

        # --- Data Cleaning ---
        # 1. Check if 'glucose' column exists
        if 'glucose' not in df.columns:
            logger.warning(
                f' - ERROR: "glucose" column not found in {filename}. Skipping.')
            # Return error indicators
            return filename, 'ERROR: glucose column missing', 'ERROR: glucose column missing', 0

        # 2. Replace placeholder -1 with NaN and convert column to numeric
        df['glucose'] = df['glucose'].replace(
            '-1', np.nan)  # Replace string '-1' with NaN
        # Convert to numeric, non-convertible become NaN
        df['glucose'] = pd.to_numeric(df['glucose'], errors='coerce')

        # 3. Get the glucose column and drop NaNs for calculation
        valid_glucose = df['glucose'].dropna()
        valid_count = len(valid_glucose)  # Count of non-NaN values

        # --- Calculate Stats ---
        if valid_count > 1:  # Need at least 2 data points for standard deviation
            mean_g = valid_glucose.mean()
            std_g = valid_glucose.std()  # Default ddof=1 (sample standard deviation)
            logger.info(
                f' - Valid readings: {valid_count}, Mean: {mean_g:.2f}, Std Dev: {std_g:.2f}')
            return filename, mean_g, std_g, valid_count
        elif valid_count == 1:  # Can calculate mean but not standard deviation
            mean_g = valid_glucose.iloc[0]
            std_g = 'N/A (only 1 reading)'  # Cannot calculate std dev
            logger.info(
                f' - Valid readings: {valid_count}, Mean: {mean_g:.2f}, Std Dev: N/A (only 1 reading)')
            return filename, mean_g, std_g, valid_count
        else:  # valid_count is 0
            logger.warning(
                f' - No valid glucose readings found in {filename}.')
            return filename, 'N/A', 'N/A', 0  # Return indicators for no data

    except Exception as e:
        logger.error(f' - ERROR processing {filename}: {e}')
        # Use string representation of error for logging in CSV
        # Return error indicators for other exceptions
        return filename, f'ERROR: {e}', f'ERROR: {e}', 0


def main():
    parser = argparse.ArgumentParser(
        description="Calculate glucose mean and standard deviation from CSV files in a directory.")
    parser.add_argument(
        '-i', '--input_dir',
        type=str,
        default='./algorithm/GluPred/data',
        help='Directory containing the CSV files.'
    )
    parser.add_argument(
        '-o', '--output_log',
        type=str,
        default='glucose_stats_log.csv',  # Default log file name
        help='Output CSV file path for the statistics log.'
    )

    args = parser.parse_args()

    input_directory = pathlib.Path(args.input_dir)
    output_log_file = pathlib.Path(args.output_log)

    # Validate input directory
    if not input_directory.is_dir():
        logger.error(
            f"Error: Input directory not found or is not a directory: {input_directory}")
        sys.exit(1)

    # Prepare the output log file
    try:
        # Use 'w' mode to overwrite if file exists, 'a' to append
        # Use newline='' for proper CSV writing across different OS
        with open(output_log_file, 'w', newline='', encoding='utf-8') as f:
            # Write header
            f.write('filename,mean_glucose,std_dev_glucose,valid_readings_count\n')

            # Process each CSV file in the directory
            # Filter for files ending with .csv
            # Sort files for consistent order
            csv_files = sorted(list(input_directory.glob('*.csv')))
            if not csv_files:
                logger.warning(
                    f"No .csv files found in directory: {input_directory}")

            for csv_file_path in csv_files:
                # Calculate stats for the current file
                filename, mean_g, std_g, valid_count = calculate_glucose_stats(
                    csv_file_path)

                # Write results to the log file
                # Ensure that numeric values are formatted and non-numeric are handled
                mean_str = f'{mean_g:.2f}' if isinstance(
                    mean_g, float) else str(mean_g)
                std_str = f'{std_g:.2f}' if isinstance(
                    std_g, float) else str(std_g)
                valid_count_str = str(valid_count)

                f.write(f'{filename},{mean_str},{std_str},{valid_count_str}\n')

        logger.info(
            f"\nProcessing complete. Results saved to '{output_log_file}'")

    except IOError as e:
        logger.error(
            f"Error writing to output log file {output_log_file}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
