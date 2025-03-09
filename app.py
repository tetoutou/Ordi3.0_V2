from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from api_error_handler import api_error_handler
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)

# Configuration conditionnelle de la base de données
if os.environ.get('VERCEL_REGION'):  # Vérifier si nous sommes sur Vercel
    # En production sur Vercel, nous utilisons une base de données en mémoire
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
else:
    # En développement local, nous utilisons un fichier SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ordi3.db'

app.config['SECRET_KEY'] = 'dev-key-replace-in-production'
db = SQLAlchemy(app)

# Configuration de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Modèles de données
class DemandeEnlevement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    heure = db.Column(db.String(5), nullable=False)  # Format HH:MM
    entreprise = db.Column(db.String(100), nullable=False)
    adresse = db.Column(db.String(200), nullable=False)
    departement = db.Column(db.String(3), nullable=False)  # Format: 01 à 95, 2A, 2B, etc.
    contact = db.Column(db.String(100))
    email = db.Column(db.String(100))
    telephone = db.Column(db.String(20))
    notes = db.Column(db.Text)
    statut = db.Column(db.String(50), default='Planifié')
    equipements = db.Column(db.JSON)  # Stockage des équipements en JSON

class EquipementStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)  # Ordinateur, Écran, etc.
    marque = db.Column(db.String(50), nullable=False)
    modele = db.Column(db.String(100), nullable=False)
    etat = db.Column(db.String(50), nullable=False)  # neuf, bon, moyen, à reconditionner
    quantite = db.Column(db.Integer, nullable=False)
    emplacement_zone = db.Column(db.String(50))
    emplacement_etagere = db.Column(db.String(50))
    date_ajout = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    seuil_alerte = db.Column(db.Integer, default=5)
    description = db.Column(db.Text)
    departement = db.Column(db.String(3))  # Code du département
    etat_reconditionnement = db.Column(db.String(50), default='a_traiter')  # a_traiter, en_cours, a_reconditionner, reconditionne
    id_reconditionnement = db.Column(db.Integer, unique=True)  # ID unique pour le suivi du reconditionnement

class Reconditionnement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_serie = db.Column(db.String(100), unique=True)
    type = db.Column(db.String(100), nullable=False)
    marque = db.Column(db.String(100), nullable=False)
    modele = db.Column(db.String(100), nullable=False)
    etat_initial = db.Column(db.String(50), nullable=False)
    provenance = db.Column(db.String(100))
    departement = db.Column(db.String(3), nullable=False)
    date_arrivee = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    date_debut = db.Column(db.DateTime)  # Date de début du reconditionnement
    
    # Étapes du processus avec techniciens
    technicien_reception = db.Column(db.String(100))  # Technicien pour la réception
    diagnostic_initial = db.Column(db.Text)
    diagnostic_date = db.Column(db.DateTime)
    technicien_diagnostic = db.Column(db.String(100))  # Technicien pour le diagnostic
    nettoyage_effectue = db.Column(db.Boolean, default=False)
    nettoyage_date = db.Column(db.DateTime)
    technicien_nettoyage = db.Column(db.String(100))  # Technicien pour le nettoyage
    composants_remplaces = db.Column(db.JSON)  # Liste des composants remplacés
    reparations_effectuees = db.Column(db.JSON)  # Liste des réparations
    technicien_reparation = db.Column(db.String(100))  # Technicien pour la réparation
    tests_effectues = db.Column(db.JSON)  # Résultats des tests
    technicien_tests = db.Column(db.String(100))  # Technicien pour les tests
    logiciels_installes = db.Column(db.JSON)  # Liste des logiciels installés
    technicien_logiciels = db.Column(db.String(100))  # Technicien pour l'installation des logiciels
    
    # Notes pour chaque étape
    notes_reception = db.Column(db.Text)  # Notes pour l'étape de réception
    notes_diagnostic = db.Column(db.Text)  # Notes pour l'étape de diagnostic
    notes_nettoyage = db.Column(db.Text)  # Notes pour l'étape de nettoyage et réparation
    notes_tests = db.Column(db.Text)  # Notes pour l'étape de tests et mises à jour
    
    # Suivi du processus
    statut = db.Column(db.String(50), nullable=False, default='en_attente')  # en_attente, diagnostic, nettoyage, reparation, tests, logiciels, termine, non_reparable
    localisation = db.Column(db.String(50))  # Zone actuelle (réception, atelier, tests, stockage)
    notes = db.Column(db.Text)
    date_fin = db.Column(db.DateTime)
    cout_total = db.Column(db.Float)
    
    # Statistiques
    temps_total = db.Column(db.Integer)  # Temps total en minutes
    succes_reparation = db.Column(db.Boolean)
    evaluation_qualite = db.Column(db.Integer)  # Note sur 5

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    role = db.Column(db.String(20))  # 'utilisateur', 'technicien', 'responsable', 'super_admin'
    departement = db.Column(db.String(3))
    actif = db.Column(db.Boolean, default=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    derniere_connexion = db.Column(db.DateTime)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role not in roles:
                flash('Accès non autorisé')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password) and user.actif:
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Email ou mot de passe incorrect')
            return render_template('login.html', error='Email ou mot de passe incorrect')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f"Erreur sur la route principale: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/enlevement')
@login_required
def enlevement():
    return render_template('enlevement.html')

@app.route('/api/enlevements', methods=['GET'])
@api_error_handler
def get_enlevements():
    print("Récupération des demandes")  # Debug
    demandes = DemandeEnlevement.query.order_by(DemandeEnlevement.date.desc()).all()
    return jsonify([{
        'id': demande.id,
        'date': demande.date.strftime('%Y-%m-%d'),
        'heure': demande.heure,
        'entreprise': demande.entreprise,
        'adresse': demande.adresse,
        'departement': demande.departement,
        'contact': demande.contact,
        'email': demande.email,
        'telephone': demande.telephone,
        'notes': demande.notes,
        'equipements': demande.equipements,
        'statut': demande.statut
    } for demande in demandes])

@app.route('/api/enlevements', methods=['POST'])
@api_error_handler
def create_enlevement():
    data = request.json
    try:
        nouvelle_demande = DemandeEnlevement(
            date=datetime.strptime(data['date'], '%Y-%m-%d'),
            heure=data['heure'],
            entreprise=data['entreprise'],
            adresse=data['adresse'],
            departement=data['departement'],
            contact=data['contact'],
            email=data['email'],
            telephone=data['telephone'],
            notes=data.get('notes', ''),
            equipements=data['equipements'],
            statut='Planifié'
        )
        db.session.add(nouvelle_demande)
        db.session.commit()
        return jsonify({'message': 'Demande créée avec succès'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/enlevements/<int:id>', methods=['PUT'])
@api_error_handler
def update_enlevement(id):
    demande = DemandeEnlevement.query.get_or_404(id)
    data = request.json
    
    if 'statut' in data:
        demande.statut = data['statut']
    
    if 'entreprise' in data:
        demande.entreprise = data['entreprise']
    if 'contact' in data:
        demande.contact = data['contact']
    if 'telephone' in data:
        demande.telephone = data['telephone']
    if 'description' in data:
        demande.description = data['description']
    if 'email' in data:
        demande.email = data['email']
    
    db.session.commit()
    return jsonify({'message': 'Demande mise à jour avec succès'})

@app.route('/api/enlevements/<int:id>', methods=['GET'])
@api_error_handler
def get_enlevement(id):
    demande = DemandeEnlevement.query.get_or_404(id)
    return jsonify({
        'id': demande.id,
        'date': demande.date.strftime('%Y-%m-%d %H:%M'),
        'entreprise': demande.entreprise,
        'contact': demande.contact,
        'telephone': demande.telephone,
        'description': demande.description,
        'email': demande.email,
        'statut': demande.statut
    })

@app.route('/api/enlevements/<int:id>', methods=['DELETE'])
@api_error_handler
def delete_enlevement(id):
    try:
        demande = DemandeEnlevement.query.get_or_404(id)
        db.session.delete(demande)
        db.session.commit()
        return jsonify({'message': 'Demande supprimée avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Routes pour la gestion du stock
@app.route('/api/stock', methods=['GET'])
@api_error_handler
def get_stock():
    equipements = EquipementStock.query.all()
    return jsonify([{
        'id': e.id,
        'type': e.type,
        'marque': e.marque,
        'modele': e.modele,
        'etat': e.etat,
        'quantite': e.quantite,
        'emplacement': {
            'zone': e.emplacement_zone,
            'etagere': e.emplacement_etagere
        },
        'date_ajout': e.date_ajout.strftime('%d/%m/%Y'),
        'seuil_alerte': e.seuil_alerte,
        'description': e.description,
        'departement': e.departement,
        'etat_reconditionnement': e.etat_reconditionnement,
        'id_reconditionnement': e.id_reconditionnement
    } for e in equipements])

@app.route('/api/stock', methods=['POST'])
@api_error_handler
def add_stock():
    data = request.json
    nouvel_equipement = EquipementStock(
        type=data['type'],
        marque=data['marque'],
        modele=data['modele'],
        etat=data['etat'],
        quantite=data['quantite'],
        seuil_alerte=data.get('seuil_alerte', 5),
        description=data.get('description', ''),
        departement=data.get('departement'),
        etat_reconditionnement=data.get('etat_reconditionnement', 'a_traiter')
    )
    db.session.add(nouvel_equipement)
    db.session.commit()
    return jsonify({'message': 'Équipement ajouté avec succès'}), 201

@app.route('/api/stock/<int:id>', methods=['PUT'])
@api_error_handler
def update_stock(id):
    equipement = EquipementStock.query.get_or_404(id)
    data = request.json
    equipement.quantite = data.get('quantite', equipement.quantite)
    equipement.etat = data.get('etat', equipement.etat)
    equipement.emplacement_zone = data.get('emplacement', {}).get('zone', equipement.emplacement_zone)
    equipement.emplacement_etagere = data.get('emplacement', {}).get('etagere', equipement.emplacement_etagere)
    equipement.seuil_alerte = data.get('seuil_alerte', equipement.seuil_alerte)
    equipement.departement = data.get('departement', equipement.departement)
    db.session.commit()
    return jsonify({'message': 'Équipement mis à jour avec succès'})

@app.route('/api/stock/<int:id>', methods=['DELETE'])
@api_error_handler
def delete_stock(id):
    try:
        equipement = EquipementStock.query.get_or_404(id)
        db.session.delete(equipement)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock/<int:id>', methods=['GET'])
@api_error_handler
def get_equipement(id):
    equipement = EquipementStock.query.get_or_404(id)
    return jsonify({
        'id': equipement.id,
        'type': equipement.type,
        'marque': equipement.marque,
        'modele': equipement.modele,
        'etat': equipement.etat,
        'quantite': equipement.quantite,
        'emplacement': {
            'zone': equipement.emplacement_zone,
            'etagere': equipement.emplacement_etagere
        },
        'seuil_alerte': equipement.seuil_alerte,
        'description': equipement.description,
        'departement': equipement.departement
    })

@app.route('/api/stock/alertes', methods=['GET'])
@api_error_handler
def get_alertes_stock():
    alertes = EquipementStock.query.filter(
        EquipementStock.quantite <= EquipementStock.seuil_alerte
    ).all()
    return jsonify([{
        'id': e.id,
        'type': e.type,
        'marque': e.marque,
        'modele': e.modele,
        'quantite': e.quantite,
        'seuil_alerte': e.seuil_alerte
    } for e in alertes])

@app.route('/stock')
@role_required(['technicien', 'responsable', 'super_admin'])
def stock_page():
    return render_template('stock.html')  # Assurez-vous d'avoir un fichier stock.html

@app.route('/reconditionnement')
@role_required(['technicien', 'responsable', 'super_admin'])
def reconditionnement_page():
    return render_template('reconditionnement.html')

@app.route('/api/reconditionnement', methods=['GET'])
def get_reconditionnements():
    equipements = Reconditionnement.query.all()
    return jsonify([{
        'id': e.id,
        'numero_serie': e.numero_serie,
        'type': e.type,
        'marque': e.marque,
        'modele': e.modele,
        'etat_initial': e.etat_initial,
        'provenance': e.provenance,
        'departement': e.departement,
        'date_arrivee': e.date_arrivee.isoformat() if e.date_arrivee else None,
        'date_debut': e.date_debut.isoformat() if e.date_debut else None,
        'technicien_reception': e.technicien_reception,
        'technicien_diagnostic': e.technicien_diagnostic,
        'technicien_nettoyage': e.technicien_nettoyage,
        'technicien_reparation': e.technicien_reparation,
        'technicien_tests': e.technicien_tests,
        'technicien_logiciels': e.technicien_logiciels,
        'diagnostic_initial': e.diagnostic_initial,
        'diagnostic_date': e.diagnostic_date.isoformat() if e.diagnostic_date else None,
        'nettoyage_effectue': e.nettoyage_effectue,
        'nettoyage_date': e.nettoyage_date.isoformat() if e.nettoyage_date else None,
        'composants_remplaces': e.composants_remplaces,
        'reparations_effectuees': e.reparations_effectuees,
        'tests_effectues': e.tests_effectues,
        'logiciels_installes': e.logiciels_installes,
        'statut': e.statut,
        'localisation': e.localisation,
        'notes': e.notes,
        'notes_reception': e.notes_reception,
        'notes_diagnostic': e.notes_diagnostic,
        'notes_nettoyage': e.notes_nettoyage,
        'notes_tests': e.notes_tests,
        'date_fin': e.date_fin.isoformat() if e.date_fin else None,
        'cout_total': e.cout_total,
        'temps_total': e.temps_total,
        'succes_reparation': e.succes_reparation,
        'evaluation_qualite': e.evaluation_qualite
    } for e in equipements])

@app.route('/api/reconditionnement', methods=['POST'])
@api_error_handler
def create_reconditionnement():
    data = request.json
    nouvel_equipement = Reconditionnement(
        numero_serie=data['numero_serie'],
        type=data['type'],
        marque=data['marque'],
        modele=data['modele'],
        etat_initial=data['etat_initial'],
        provenance=data.get('provenance'),
        departement=data['departement'],
        localisation='reception'
    )
    db.session.add(nouvel_equipement)
    db.session.commit()
    return jsonify({'message': 'Équipement ajouté avec succès', 'id': nouvel_equipement.id}), 201

@app.route('/api/reconditionnement/<int:id>', methods=['PUT'])
@api_error_handler
def update_reconditionnement(id):
    equipement = Reconditionnement.query.get_or_404(id)
    data = request.json

    # Mise à jour des champs de base
    if 'type' in data:
        equipement.type = data['type']
    if 'marque' in data:
        equipement.marque = data['marque']
    if 'modele' in data:
        equipement.modele = data['modele']
    if 'etat_initial' in data:
        equipement.etat_initial = data['etat_initial']
    if 'provenance' in data:
        equipement.provenance = data['provenance']
    if 'departement' in data:
        equipement.departement = data['departement']

    # Mise à jour des techniciens par étape
    if 'technicien_reception' in data:
        equipement.technicien_reception = data['technicien_reception']
    if 'technicien_diagnostic' in data:
        equipement.technicien_diagnostic = data['technicien_diagnostic']
    if 'technicien_nettoyage' in data:
        equipement.technicien_nettoyage = data['technicien_nettoyage']
    if 'technicien_reparation' in data:
        equipement.technicien_reparation = data['technicien_reparation']
    if 'technicien_tests' in data:
        equipement.technicien_tests = data['technicien_tests']
    if 'technicien_logiciels' in data:
        equipement.technicien_logiciels = data['technicien_logiciels']

    # Mise à jour des autres champs
    if 'diagnostic_initial' in data:
        equipement.diagnostic_initial = data['diagnostic_initial']
    if 'diagnostic_date' in data:
        equipement.diagnostic_date = datetime.fromisoformat(data['diagnostic_date']) if data['diagnostic_date'] else None
    if 'nettoyage_effectue' in data:
        equipement.nettoyage_effectue = data['nettoyage_effectue']
    if 'nettoyage_date' in data:
        equipement.nettoyage_date = datetime.fromisoformat(data['nettoyage_date']) if data['nettoyage_date'] else None
    if 'composants_remplaces' in data:
        equipement.composants_remplaces = data['composants_remplaces']
    if 'reparations_effectuees' in data:
        equipement.reparations_effectuees = data['reparations_effectuees']
    if 'tests_effectues' in data:
        equipement.tests_effectues = data['tests_effectues']
    if 'logiciels_installes' in data:
        equipement.logiciels_installes = data['logiciels_installes']
    if 'statut' in data:
        equipement.statut = data['statut']
    if 'localisation' in data:
        equipement.localisation = data['localisation']
    if 'notes' in data:
        equipement.notes = data['notes']
    if 'date_fin' in data:
        equipement.date_fin = datetime.fromisoformat(data['date_fin']) if data['date_fin'] else None
    if 'cout_total' in data:
        equipement.cout_total = data['cout_total']
    if 'temps_total' in data:
        equipement.temps_total = data['temps_total']
    if 'succes_reparation' in data:
        equipement.succes_reparation = data['succes_reparation']
    if 'evaluation_qualite' in data:
        equipement.evaluation_qualite = data['evaluation_qualite']

    # Mise à jour des notes par étape
    if 'notes_reception' in data:
        equipement.notes_reception = data['notes_reception']
    if 'notes_diagnostic' in data:
        equipement.notes_diagnostic = data['notes_diagnostic']
    if 'notes_nettoyage' in data:
        equipement.notes_nettoyage = data['notes_nettoyage']
    if 'notes_tests' in data:
        equipement.notes_tests = data['notes_tests']

    db.session.commit()
    return jsonify({'message': 'Équipement mis à jour avec succès'})

@app.route('/api/reconditionnement/<int:id>', methods=['GET'])
@api_error_handler
def get_reconditionnement_detail(id):
    equipement = Reconditionnement.query.get_or_404(id)
    return jsonify({
        'id': equipement.id,
        'numero_serie': equipement.numero_serie,
        'type': equipement.type,
        'marque': equipement.marque,
        'modele': equipement.modele,
        'etat_initial': equipement.etat_initial,
        'provenance': equipement.provenance,
        'departement': equipement.departement,
        'date_arrivee': equipement.date_arrivee.isoformat(),
        'diagnostic_initial': equipement.diagnostic_initial,
        'diagnostic_date': equipement.diagnostic_date.isoformat() if equipement.diagnostic_date else None,
        'nettoyage_effectue': equipement.nettoyage_effectue,
        'nettoyage_date': equipement.nettoyage_date.isoformat() if equipement.nettoyage_date else None,
        'composants_remplaces': equipement.composants_remplaces,
        'reparations_effectuees': equipement.reparations_effectuees,
        'tests_effectues': equipement.tests_effectues,
        'logiciels_installes': equipement.logiciels_installes,
        'statut': equipement.statut,
        'localisation': equipement.localisation,
        'technicien': equipement.technicien_reception,
        'notes': equipement.notes,
        'date_fin': equipement.date_fin.isoformat() if equipement.date_fin else None,
        'cout_total': equipement.cout_total,
        'temps_total': equipement.temps_total,
        'succes_reparation': equipement.succes_reparation,
        'evaluation_qualite': equipement.evaluation_qualite
    })

@app.route('/api/reconditionnement/statistiques', methods=['GET'])
@api_error_handler
def get_statistiques_reconditionnement():
    total = Reconditionnement.query.count()
    termines = Reconditionnement.query.filter_by(statut='termine').count()
    non_reparables = Reconditionnement.query.filter_by(statut='non_reparable').count()
    en_cours = total - termines - non_reparables
    
    temps_moyen = db.session.query(db.func.avg(Reconditionnement.temps_total)).filter(
        Reconditionnement.temps_total.isnot(None)
    ).scalar()
    
    taux_succes = db.session.query(
        db.func.sum(db.case([(Reconditionnement.succes_reparation == True, 1)], else_=0)) * 100.0 / 
        db.func.count(Reconditionnement.id)
    ).filter(Reconditionnement.statut == 'termine').scalar()
    
    evaluation_moyenne = db.session.query(db.func.avg(Reconditionnement.evaluation_qualite)).filter(
        Reconditionnement.evaluation_qualite.isnot(None)
    ).scalar()
    
    return jsonify({
        'total': total,
        'en_cours': en_cours,
        'termines': termines,
        'non_reparables': non_reparables,
        'temps_moyen_minutes': temps_moyen,
        'taux_succes': taux_succes,
        'evaluation_moyenne': evaluation_moyenne
    })

@app.route('/api/reconditionnement/<int:id>/demarrer', methods=['PUT'])
@api_error_handler
def demarrer_reconditionnement(id):
    equipement = Reconditionnement.query.get_or_404(id)
    equipement.statut = 'en_cours'
    equipement.date_debut = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Reconditionnement démarré avec succès'})

@app.route('/api/reconditionnement/<int:id>/etape/<string:etape>', methods=['PUT'])
@api_error_handler
def update_etape_reconditionnement(id, etape):
    equipement = Reconditionnement.query.get_or_404(id)
    data = request.json
    
    # Mise à jour des champs en fonction de l'étape
    if etape == 'diagnostic':
        equipement.diagnostic_date = datetime.utcnow() if data.get('diagnostic_date') else None
        if equipement.diagnostic_date:
            equipement.statut = 'diagnostic'
    
    elif etape == 'nettoyage':
        equipement.nettoyage_effectue = data.get('nettoyage_effectue', False)
        equipement.nettoyage_date = datetime.utcnow() if equipement.nettoyage_effectue else None
        if equipement.nettoyage_effectue:
            equipement.statut = 'nettoyage'
    
    elif etape == 'reparation':
        equipement.composants_remplaces = data.get('composants_remplaces', [])
        if equipement.composants_remplaces:
            equipement.statut = 'reparation'
    
    elif etape == 'tests':
        equipement.tests_effectues = data.get('tests_effectues', [])
        if equipement.tests_effectues:
            equipement.statut = 'tests'
    
    elif etape == 'logiciels':
        equipement.logiciels_installes = data.get('logiciels_installes', [])
        if equipement.logiciels_installes:
            equipement.statut = 'logiciels'
    
    # Mise à jour du statut global
    if all([
        equipement.diagnostic_date,
        equipement.nettoyage_effectue,
        equipement.composants_remplaces,
        equipement.tests_effectues,
        equipement.logiciels_installes
    ]):
        equipement.statut = 'termine'
        equipement.date_fin = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'message': 'Étape mise à jour avec succès'})

@app.route('/utilisateurs')
@role_required(['responsable', 'super_admin'])
def utilisateurs_page():
    return render_template('utilisateurs.html')

@app.route('/api/utilisateurs', methods=['GET'])
@api_error_handler
def get_utilisateurs():
    utilisateurs = User.query.all()
    return jsonify([{
        'id': u.id,
        'nom': u.nom,
        'prenom': u.prenom,
        'email': u.email,
        'role': u.role,
        'departement': u.departement,
        'actif': u.actif
    } for u in utilisateurs])

@app.route('/api/utilisateurs', methods=['POST'])
@api_error_handler
def create_utilisateur():
    data = request.json
    from werkzeug.security import generate_password_hash
    
    nouvel_utilisateur = User(
        nom=data['nom'],
        prenom=data['prenom'],
        email=data['email'],
        password=generate_password_hash(data['password']),
        role=data['role'],
        departement=data.get('departement')
    )
    db.session.add(nouvel_utilisateur)
    db.session.commit()
    return jsonify({'message': 'Utilisateur créé avec succès'}), 201

@app.route('/api/utilisateurs/<int:id>', methods=['PUT'])
@api_error_handler
def update_utilisateur(id):
    utilisateur = User.query.get_or_404(id)
    data = request.json
    
    if 'nom' in data:
        utilisateur.nom = data['nom']
    if 'prenom' in data:
        utilisateur.prenom = data['prenom']
    if 'email' in data:
        utilisateur.email = data['email']
    if 'role' in data:
        utilisateur.role = data['role']
    if 'departement' in data:
        utilisateur.departement = data['departement']
    if 'actif' in data:
        utilisateur.actif = data['actif']
    if 'password' in data and data['password']:
        from werkzeug.security import generate_password_hash
        utilisateur.password = generate_password_hash(data['password'])
    
    db.session.commit()
    return jsonify({'message': 'Utilisateur mis à jour avec succès'})

@app.route('/api/utilisateurs/<int:id>', methods=['DELETE'])
@api_error_handler
def delete_utilisateur(id):
    utilisateur = User.query.get_or_404(id)
    db.session.delete(utilisateur)
    db.session.commit()
    return jsonify({'message': 'Utilisateur supprimé avec succès'})

@app.cli.command("create-admin")
def create_admin():
    """Crée un compte super administrateur par défaut."""
    admin = User.query.filter_by(email='admin@ordi3.fr').first()
    if admin:
        print('Le compte admin existe déjà.')
        return

    admin = User(
        email='admin@ordi3.fr',
        password=generate_password_hash('admin123'),  # À changer en production !
        nom='Admin',
        prenom='Super',
        role='super_admin',
        departement='75',
        actif=True
    )
    db.session.add(admin)
    db.session.commit()
    print('Compte super administrateur créé avec succès.')
    print('Email: admin@ordi3.fr')
    print('Mot de passe: admin123')

with app.app_context():
    try:
        # Tenter de supprimer les tables existantes
        db.drop_all()
    except Exception as e:
        print(f"Note: {str(e)}")  # Les tables n'existent peut-être pas encore
    
    # Créer toutes les tables
    db.create_all()
    
    # Charger des données de démonstration si nous sommes sur Vercel
    if os.environ.get('VERCEL_REGION') and EquipementStock.query.count() == 0:
        try:
            # Ajouter quelques demandes d'enlèvement de démonstration
            demo_enlevement1 = DemandeEnlevement(
                date=datetime.now(),
                entreprise="Société Démo",
                contact="Jean Demo",
                email="contact@demo.fr",
                telephone="0123456789",
                description="Lot de 10 ordinateurs portables",
                statut="Planifié"
            )
            
            demo_enlevement2 = DemandeEnlevement(
                date=datetime.now(),
                entreprise="Entreprise Test",
                contact="Marie Test",
                email="info@test.fr",
                telephone="0987654321",
                description="5 écrans et 2 serveurs",
                statut="En cours"
            )
            
            # Ajouter des équipements de stock de démonstration
            demo_equipement1 = EquipementStock(
                type="Ordinateur",
                marque="Dell",
                modele="Latitude 7420",
                etat="bon",
                quantite=5,
                seuil_alerte=2,
                description="Ordinateurs portables reconditionnés"
            )
            
            demo_equipement2 = EquipementStock(
                type="Écran",
                marque="HP",
                modele="E24 G4",
                etat="neuf",
                quantite=3,
                seuil_alerte=1,
                description="Écrans 24 pouces"
            )
            
            db.session.add(demo_enlevement1)
            db.session.add(demo_enlevement2)
            db.session.add(demo_equipement1)
            db.session.add(demo_equipement2)
            db.session.commit()
            
            print("Données de démonstration ajoutées avec succès")
        except Exception as e:
            print(f"Erreur lors de l'ajout des données de démonstration: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    app.run(debug=True)
