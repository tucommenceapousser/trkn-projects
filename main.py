import os
import zipfile
from flask import Flask, render_template, send_file, request, redirect, url_for, flash
import requests
from dotenv import load_dotenv
from git import Repo
import json
import time

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
GEOPENCAGE = os.getenv("GEOPENCAGE")
GEO_API_KEY = os.getenv("GEO_API_KEY")
GEO_API_URL = "https://ipinfo.io/"
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Enregistrer les logs de téléchargement
def log_download(data):
    with open("downloads.json", "a") as f:
        log_data = {**data, 'id': str(time.time())}  # Ajout d'un ID unique
        f.write(json.dumps(log_data) + "\n")

# Route principale - afficher les projets
@app.route("/")
def index():
    projects = [d for d in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, d))]
    return render_template("index.html", projects=projects)

LOG_FILE = "downloads.json"
SECRET_PASSWORD = os.getenv('mdp')  # Le mot de passe secret


def load_logs():
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            logs = [json.loads(line) for line in f.readlines()]  # Charger les logs JSON
    return logs

def save_logs(logs):
    with open(LOG_FILE, 'w') as f:
        for log in logs:
            f.write(json.dumps(log) + "\n")

@app.route("/delete_log/<log_id>")
def delete_log(log_id):
    logs = load_logs()
    logs = [log for log in logs if log['id'] != log_id]  # Suppression du log avec l'id spécifié
    save_logs(logs)
    return redirect("/logs")

@app.route("/reset_logs")
def reset_logs():
    save_logs([])  # Réinitialisation des logs
    return redirect("/logs")

@app.route("/download_logs")
def download_logs():
    # Sécuriser l'accès à cette route avec un mot de passe
    return send_file(LOG_FILE, as_attachment=True)  # Téléchargement du fichier de logs

@app.route("/logs", methods=["GET", "POST"])
def view_logs():
    # Si le formulaire est soumis avec un mot de passe
    if request.method == "POST":
        password = request.form.get("password")
        
        # Vérifier si le mot de passe est correct
        if password != SECRET_PASSWORD:
            flash("Mot de passe incorrect.", "error")
            return redirect(url_for("view_logs"))
        
        logs = load_logs()
        # Récupération des coordonnées géographiques pour afficher la carte
        for log in logs:
            city = log['geo_data'].get('city', '')
            country = log['geo_data'].get('country', '')
            log['latitude'], log['longitude'] = get_coordinates(city, country)
        return render_template("logs.html", logs=logs)
    
    # Si la méthode est GET, on demande simplement un mot de passe
    return render_template("login.html")

def get_coordinates(city, country):
    # Utilisation de l'API de géolocalisation pour obtenir les coordonnées
    url = f'https://api.opencagedata.com/geocode/v1/json?q={city},{country}&key={GEOPENCAGE}'
    response = requests.get(url)
    data = response.json()
    
    if data['results']:
        lat = data['results'][0]['geometry']['lat']
        lng = data['results'][0]['geometry']['lng']
        return lat, lng
    return None, None

@app.route("/github_repos/<username>")
def github_repos(username):
    per_page = 30
    page = request.args.get('page', 1, type=int)

    github_api_url = f"https://api.github.com/users/{username}/repos?per_page={per_page}&page={page}"

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}'
    }

    response = requests.get(github_api_url, headers=headers)

    if response.status_code != 200:
        return f"Erreur : Impossible de récupérer les référentiels pour l'utilisateur {username}.", 500

    repos = response.json()

    next_page = None
    if len(repos) == per_page:
        next_page = page + 1

    prev_page = None
    if page > 1:
        prev_page = page - 1

    return render_template("github_repos.html", username=username, repos=repos, next_page=next_page, prev_page=prev_page)

def get_client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        ip = forwarded_for.split(',')[0]
    else:
        ip = request.remote_addr
    
    return ip

@app.route("/download/<project_name>")
def download(project_name):
    project_path = os.path.join(PROJECTS_DIR, project_name)
    if not os.path.exists(project_path):
        return "Projet introuvable.", 404

    zip_path = f"{project_name}.zip"
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for root, _, files in os.walk(project_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, project_path)
                zipf.write(file_path, arcname)

    visitor_ip = get_client_ip()
    geo_data = requests.get(f"{GEO_API_URL}{visitor_ip}?token={GEO_API_KEY}").json()
    user_agent = request.headers.get("User-Agent")

    log_data = {
        "ip": visitor_ip,
        "geo_data": geo_data,
        "user_agent": user_agent,
        "project": project_name,
    }
    log_download(log_data)

    response = send_file(zip_path, as_attachment=True)
    os.remove(zip_path)
    return response    

@app.route("/project/<project_name>")
def project_details(project_name):
    project_path = os.path.join(PROJECTS_DIR, project_name)
    if not os.path.exists(project_path):
        return "Projet introuvable.", 404

    contents = []
    for root, dirs, files in os.walk(project_path):
        for name in dirs:
            contents.append(os.path.relpath(os.path.join(root, name), project_path))
        for name in files:
            contents.append(os.path.relpath(os.path.join(root, name), project_path))

    return render_template("project.html", project_name=project_name, contents=contents)

@app.route("/add_project", methods=["GET", "POST"])
def add_project():
    if request.method == "POST":
        github_url = request.form.get("github_url")
        if not github_url:
            flash("URL du référentiel GitHub manquante.", "error")
            return redirect(url_for("index"))

        try:
            project_name = github_url.split("/")[-1].replace(".git", "")
            project_path = os.path.join(PROJECTS_DIR, project_name)

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
