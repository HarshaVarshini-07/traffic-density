import shutil
import os
import datetime

def zip_training_data():
    project_root = os.path.dirname(os.path.abspath(__file__))
    training_dir = os.path.join(project_root, 'tools', 'training_data')
    
    if not os.path.exists(training_dir):
        print(f"Error: {training_dir} does not exist!")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"smart_traffic_training_data_{timestamp}"
    output_path = os.path.join(project_root, zip_filename)
    
    print(f"Zipping {training_dir}...")
    shutil.make_archive(output_path, 'zip', training_dir)
    print(f"Created: {output_path}.zip")

if __name__ == "__main__":
    zip_training_data()
