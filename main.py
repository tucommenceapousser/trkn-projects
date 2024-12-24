import os
import zipfile
from flask import Flask, render_template, send_file, request, redirect, url_for, flash
import requests
from dotenv import load_dotenv
from git import Repo  # GitPython pour cloner des repositories

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Nécessaire pour les messages flash

# Dossier contenant les projets
PROJECTS_DIR = "projects"

# Vérifier et créer le dossier projects s'il n'existe pas
if not os.path.exists(PROJECTS_DIR):
    os.makedirs(PROJECTS_DIR)

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

# Route pour afficher les référentiels publics d'un utilisateur GitHub
@app.route("/github_repos/<username>")
def github_repos(username):
    github_api_url = f"https://api.github.com/users/{username}/repos"
    response = requests.get(github_api_url)

    if response.status_code != 200:
        return f"Erreur : Impossible de récupérer les référentiels pour l'utilisateur {username}.", 500

    repos = response.json()
    return render_template("github_repos.html", username=username, repos=repos)
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

    # Liste des fichiers et sous-dossiers
    contents = []
    for root, dirs, files in os.walk(project_path):
        for name in dirs:
            contents.append(os.path.relpath(os.path.join(root, name), project_path))
        for name in files:
            contents.append(os.path.relpath(os.path.join(root, name), project_path))

    return render_template("project.html", project_name=project_name, contents=contents)
# Route pour ajouter un projet depuis GitHub
@app.route("/add_project", methods=["GET", "POST"])
def add_project():
    if request.method == "POST":
        github_url = request.form.get("github_url")
        if not github_url:
            flash("URL du référentiel GitHub manquante.", "error")
            return redirect(url_for("add_project"))

        try:
            # Nom du projet basé sur le dernier segment de l'URL
            project_name = github_url.split("/")[-1].replace(".git", "")
            project_path = os.path.join(PROJECTS_DIR, project_name)

            # Cloner le référentiel GitHub
            if os.path.exists(project_path):
                flash(f"Le projet '{project_name}' existe déjà.", "error")
            else:
                Repo.clone_from(github_url, project_path)
                flash(f"Le projet '{project_name}' a été ajouté avec succès.", "success")
        except Exception as e:
            flash(f"Erreur lors du clonage : {e}", "error")

        return redirect(url_for("index"))

    return render_template("add_project.html")

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")
