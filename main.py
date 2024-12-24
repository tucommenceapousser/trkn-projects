import os
import zipfile
from flask import Flask, render_template, send_file, request
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)

# Dossier contenant les projets
PROJECTS_DIR = "projects"

# API pour géolocalisation
GEO_API_KEY = os.getenv("GEO_API_KEY")
GEO_API_URL = "https://ipinfo.io/"
# Enregistrer les logs de téléchargement
def log_download(data):
    with open("downloads.log", "a") as f:
        f.write(f"{data}\n")

# Route principale - afficher les projets
@app.route("/")
def index():
    projects = [d for d in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, d))]
    return render_template("index.html", projects=projects)

# Route pour télécharger un projet
@app.route("/download/<project_name>")
def download(project_name):
    project_path = os.path.join(PROJECTS_DIR, project_name)
    if not os.path.exists(project_path):
        return "Projet introuvable.", 404

    # Création dynamique d'un zip
    zip_path = f"{project_name}.zip"
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for root, _, files in os.walk(project_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, project_path)
                zipf.write(file_path, arcname)

    # Récupération des informations du visiteur
    visitor_ip = request.remote_addr
    geo_data = requests.get(f"{GEO_API_URL}{visitor_ip}?token={GEO_API_KEY}").json()
    user_agent = request.headers.get("User-Agent")

    # Log des données
    log_data = {
        "ip": visitor_ip,
        "geo_data": geo_data,
        "user_agent": user_agent,
        "project": project_name,
    }
    log_download(log_data)

    # Envoi du fichier zip
    response = send_file(zip_path, as_attachment=True)
    os.remove(zip_path)  # Supprimer le fichier zip après envoi
    return response

# Route pour voir les détails d'un projet
@app.route("/project/<project_name>")
def project_details(project_name):
    project_path = os.path.join(PROJECTS_DIR, project_name)
    if not os.path.exists(project_path):
        return "Projet introuvable.", 404

    return render_template("project.html", project_name=project_name)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")
