from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from api_error_handler import api_error_handler

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

# Modèles de données
class DemandeEnlevement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    entreprise = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100))
    email = db.Column(db.String(100))
    telephone = db.Column(db.String(20))
    description = db.Column(db.Text)
    statut = db.Column(db.String(50), default='Planifié')

class EquipementStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)  # Ordinateur, Écran, etc.
    marque = db.Column(db.String(50), nullable=False)
    modele = db.Column(db.String(100), nullable=False)
    etat = db.Column(db.String(50), nullable=False)  # neuf, bon, moyen, à reconditionner
    quantite = db.Column(db.Integer, nullable=False)
    emplacement_zone = db.Column(db.String(50), nullable=False)
    emplacement_etagere = db.Column(db.String(50), nullable=False)
    date_ajout = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    seuil_alerte = db.Column(db.Integer, default=5)
    description = db.Column(db.Text)

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f"Erreur sur la route principale: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/enlevements', methods=['GET'])
@api_error_handler
def get_enlevements():
    print("Récupération des demandes")  # Debug
    demandes = DemandeEnlevement.query.order_by(DemandeEnlevement.date.desc()).all()
    return jsonify([{
        'id': demande.id,
        'date': demande.date.strftime('%Y-%m-%d %H:%M'),
        'entreprise': demande.entreprise,
        'contact': demande.contact,
        'telephone': demande.telephone,
        'description': demande.description,
        'statut': demande.statut
    } for demande in demandes])

@app.route('/api/enlevements', methods=['POST'])
@api_error_handler
def create_enlevement():
    data = request.json
    try:
        date = datetime.strptime(data['date'], '%Y-%m-%d')
        nouvelle_demande = DemandeEnlevement(
            date=date,
            entreprise=data['entreprise'],
            contact=data['contact'],
            email=data['email'],
            telephone=data['telephone'],
            description=data['description'],
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
        'description': e.description
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
        emplacement_zone=data['emplacement']['zone'],
        emplacement_etagere=data['emplacement']['etagere'],
        seuil_alerte=data.get('seuil_alerte', 5),
        description=data.get('description', '')
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
        'description': equipement.description
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

with app.app_context():
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
