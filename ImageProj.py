import cv2
import pytesseract
from threading import Thread, Lock, Semaphore
from queue import Queue
from tqdm import tqdm
import threading
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import numpy as np

def extract_data_from_image(image_path):
    print(f"Thread {threading.get_ident()} - Extraction de l'image: {image_path}")
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    
    text = pytesseract.image_to_string(binary_image)
    return binary_image, text

def process_image(data_lock, final_data, semaphore, queue, progress_bar):
    while not queue.empty():
        image_path = queue.get()
        print(f"Thread {threading.get_ident()} starting for image: {image_path}")
        binary_image, text = extract_data_from_image(image_path)
        student_data = parse_data(text)
        
        semaphore.acquire()  # Acquérir le sémaphore
        data_lock.acquire()  # Acquérir le verrou
        try:
            for student, statuses in student_data.items():
                if student in final_data:
                    final_data[student].extend(statuses)
                else:
                    final_data[student] = statuses
        finally:
            data_lock.release()  # Libérer le verrou
            semaphore.release()  # Libérer le sémaphore

        print(f"Thread {threading.get_ident()} finished for image: {image_path}")
        queue.task_done()  # Signaler que la tâche est terminée
        progress_bar.update(1)  # Update the progress bar

def parse_data(text):
    names = text.split("Séance 1 (10h-10h30)")[0]
    names = names.split("\n")
    names_processed = [name for name in names if len(name) > 1][1:]
    seance2 = text.split("Séance 2 (10h45-12h15)")[1]
    seance2 = seance2.split("\n")
    seance2_processed = seance2[1:-1]
    seance1 = text.split("Séance 1 (10h-10h30)")[1].split("Séance 2 (10h45-12h15)")[0]
    seance1 = seance1.split("\n")
    seance1_processed = [status for status in seance1 if len(status) != 0]
    data = []
    data.append(names_processed)
    data.append(seance1_processed)
    data.append(seance2_processed)
    student_data = {names_processed[index]: [seance1_processed[index], seance2_processed[index]] for index in range(len(data[0]))}

    return student_data

def calculate_presence_absence(data):
    presence_absence_count = {}
    for student, statuses in data.items():
        presence_absence_count[student] = {
            'Present': statuses.count("present"),
            'Absent': statuses.count("absent")
        }
    return presence_absence_count

def display_results(presence_absence_count):
    result_window = tk.Toplevel()
    result_window.title("Résultats des présences/absences")
    result_window.geometry("600x400")

    columns = ["Nom", "Présent", "Absent"]
    tree = ttk.Treeview(result_window, columns=columns, show="headings")
    tree.heading("Nom", text="Nom")
    tree.heading("Présent", text="Présent")
    tree.heading("Absent", text="Absent")
    tree.pack(fill=tk.BOTH, expand=True)

    for name, counts in presence_absence_count.items():
        tree.insert("", tk.END, values=(name, counts['Present'], counts['Absent']))

def main(image_paths):
    data_lock = Lock()
    semaphore = Semaphore(3)  # Limiter à 3 threads dans la section critique
    queue = Queue()
    final_data = {}

    for image_path in image_paths:
        queue.put(image_path)

    progress_bar = tqdm(total=len(image_paths), desc="Traitement des absences", position=0, leave=True)

    threads = []
    for _ in range(5):  # Création de 5 threads
        thread = Thread(target=process_image, args=(data_lock, final_data, semaphore, queue, progress_bar))
        threads.append(thread)

    for thread in threads:
        thread.start()

    queue.join()  # Attendre que tous les éléments de la queue soient traités

    progress_bar.close()

    presence_absence_count = calculate_presence_absence(final_data)

    display_results(presence_absence_count)

def browse_files(entry):
    filenames = filedialog.askopenfilenames(title="Select Images",
                                            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])
    entry.delete(0, tk.END)
    entry.insert(0, ";".join(filenames))

def start_processing(entry):
    image_paths = entry.get().split(";")
    image_paths = [path for path in image_paths if os.path.isfile(path)]
    
    if not image_paths:
        messagebox.showerror("Erreur", "Aucun fichier image valide ou introuvable.")
        return
    
    # Run the main processing in a separate thread to keep the GUI responsive
    processing_thread = Thread(target=main, args=(image_paths,))
    processing_thread.start()

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Gestion des absences des étudiants")
    root.geometry("500x200")

    tk.Label(root, text="Chemin des images:").pack(pady=10)
    image_path_entry = tk.Entry(root, width=50)
    image_path_entry.pack(pady=5)

    browse_button = tk.Button(root, text="Parcourir", command=lambda: browse_files(image_path_entry))
    browse_button.pack(pady=5)

    process_button = tk.Button(root, text="Lancer le traitement", command=lambda: start_processing(image_path_entry))
    process_button.pack(pady=20)

    root.mainloop()