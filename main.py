import os
import zipfile
from flask import Flask, render_template, send_file, request, redirect, url_for, flash
import requests
from dotenv import load_dotenv
from git import Repo  # GitPython pour cloner des repositories

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)
app.secret_key = "trkntrkn"  # Nécessaire pour les messages flash

# Dossier contenant les projets
PROJECTS_DIR = "projects"

# Vérifier et créer le dossier projects s'il n'existe pas
if not os.path.exists(PROJECTS_DIR):
    os.makedirs(PROJECTS_DIR)

# API pour géolocalisation
GEO_API_KEY = os.getenv("GEO_API_KEY")
GEO_API_URL = "https://ipinfo.io/"
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Enregistrer les logs de téléchargement
def log_download(data):
    with open("downloads.log", "a") as f:
        f.write(f"{data}\n")

# Route principale - afficher les projets
@app.route("/")
def index():
    projects = [d for d in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, d))]
    return render_template("index.html", projects=projects)

LOG_FILE = "downloads.log"
SECRET_PASSWORD = os.getenv('mdp')  # Le mot de passe secret

@app.route("/logs", methods=["GET", "POST"])
def view_logs():
    # Si le formulaire est soumis avec un mot de passe
    if request.method == "POST":
        password = request.form.get("password")
        
        # Vérifier si le mot de passe est correct
        if password != SECRET_PASSWORD:
            flash("Mot de passe incorrect.", "error")
            return redirect(url_for("view_logs"))
        
        # Lire le fichier de logs
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as file:
                logs = file.readlines()  # Lire toutes les lignes du fichier log
        else:
            logs = []  # Si le fichier n'existe pas, retourner une liste vide

        return render_template("logs.html", logs=logs)
    
    # Si la méthode est GET, on demande simplement un mot de passe
    return render_template("login.html")

@app.route("/github_repos/<username>")
def github_repos(username):
    # Nombre de repos par page
    per_page = 30
    page = request.args.get('page', 1, type=int)  # Obtenir la page actuelle, par défaut 1

    # L'URL pour récupérer les repos avec la pagination
    github_api_url = f"https://api.github.com/users/{username}/repos?per_page={per_page}&page={page}"

    # Ajout du token d'authentification dans les headers
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}'
    }

    # Faire la requête GET avec l'en-tête d'authentification
    response = requests.get(github_api_url, headers=headers)

    if response.status_code != 200:
        return f"Erreur : Impossible de récupérer les référentiels pour l'utilisateur {username}.", 500

    repos = response.json()

    # Vérifier s'il y a encore des repos à afficher (si le nombre de repos est inférieur à `per_page`, nous sommes à la dernière page)
    next_page = None
    if len(repos) == per_page:
        next_page = page + 1

    prev_page = None
    if page > 1:
        prev_page = page - 1

    return render_template("github_repos.html", username=username, repos=repos, next_page=next_page, prev_page=prev_page)


# Route pour afficher les référentiels publics d'un utilisateur GitHub
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
            return redirect(url_for("index"))

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

    # Afficher une page où l'utilisateur peut ajouter manuellement une URL de repo
    return render_template("add_project.html")

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")
