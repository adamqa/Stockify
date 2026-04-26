#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de seeding pour la base de données de gestion de stock
Usage: python seed.py
   OU: python seed.py --clear
"""

import os
import sys
import django
from datetime import datetime, timedelta, date
from decimal import Decimal
import random
import json

# Configuration - MODIFIER SELON VOTRE PROJET
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'back.settings')

django.setup()

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum

# Import des modèles
from stock_app.models import (
    Utilisateur, Article, Lot, Emplacement, 
    Mouvement_Entree, Mouvement_Sortie, Mouvement_Sortie_externe,
    Inventaire, Comptage, Depreciation, HistoriqueAction,
    Historique_Classification_ABC, Fournisseur, CommandeFournisseur
)

# ============= CONFIGURATION =============
FAMILLES = ['MP', 'PF', 'SPF', 'P.RECH', 'consommable']
SOUS_FAMILLES = {
    'MP': ['Bois', 'Quincaillerie', 'Peinture', 'Colles', 'Abrasifs', 'Outillage'],
    'PF': ['Mobilier', 'Décoration', 'Rangement', 'Assise', 'Tables'],
    'SPF': ['Semi-fini 1', 'Semi-fini 2', 'Composants'],
    'P.RECH': ['Réactifs', 'Solvants', 'Tests qualité'],
    'consommable': ['Protection', 'Nettoyage', 'Petit outillage']
}
UNITES = ['pièce', 'kg', 'litre', 'mètre', 'boîte', 'carton', 'unité', 'jeu', 'rouleau', 'bouteille']
STATUTS_ARTICLE = ['disponible', 'bloqué', 'en contrôle', 'réservé']
STATUTS_LOT = ['disponible', 'bloqué', 'réservé', 'en contrôle']
ZONES = ['préparation', 'stockage', 'retours']
PROCHE_VALUES = [1, 20, 100]
TYPE_SORTIE_INTERNE = ['transfert_interne', 'consommation_interne', 'ajustement', 'destruction', 'échantillon']
TYPE_SORTIE_EXTERNE = ['vente', 'transfert', 'consommation']
TYPE_ENTREE = ['achat', 'transfert', 'retour']

# Zone coordinates for map
ZONE_COORDS = {
    'préparation': {'lat': 33.5731, 'lng': -7.5898, 'range': 0.1},
    'stockage': {'lat': 33.5750, 'lng': -7.5850, 'range': 0.1},
    'retours': {'lat': 33.5770, 'lng': -7.5900, 'range': 0.1}
}

# ============= DONNÉES DE TEST =============
ARTICLES_DATA = [
    # Matières Premières (MP)
    {"nom": "Panneau OSB 3 18mm", "famille": "MP", "prix": Decimal("25.50"), "seuil": 50, "unite": "pièce", "sous_famille": "Bois"},
    {"nom": "Panneau MDF 19mm", "famille": "MP", "prix": Decimal("32.00"), "seuil": 40, "unite": "pièce", "sous_famille": "Bois"},
    {"nom": "Contreplaqué 15mm", "famille": "MP", "prix": Decimal("45.00"), "seuil": 30, "unite": "pièce", "sous_famille": "Bois"},
    {"nom": "Vis à bois 3x30mm", "famille": "MP", "prix": Decimal("0.08"), "seuil": 1000, "unite": "pièce", "sous_famille": "Quincaillerie"},
    {"nom": "Vis à bois 4x40mm", "famille": "MP", "prix": Decimal("0.12"), "seuil": 800, "unite": "pièce", "sous_famille": "Quincaillerie"},
    {"nom": "Vis à bois 5x50mm", "famille": "MP", "prix": Decimal("0.18"), "seuil": 600, "unite": "pièce", "sous_famille": "Quincaillerie"},
    {"nom": "Chevilles universelles 6mm", "famille": "MP", "prix": Decimal("0.05"), "seuil": 1500, "unite": "pièce", "sous_famille": "Quincaillerie"},
    {"nom": "Colle à bois blanche 5L", "famille": "MP", "prix": Decimal("45.00"), "seuil": 20, "unite": "litre", "sous_famille": "Colles"},
    {"nom": "Colle néoprène 1L", "famille": "MP", "prix": Decimal("28.00"), "seuil": 15, "unite": "litre", "sous_famille": "Colles"},
    {"nom": "Colle epoxy 500ml", "famille": "MP", "prix": Decimal("35.00"), "seuil": 10, "unite": "boîte", "sous_famille": "Colles"},
    {"nom": "Vernis mat 2.5L", "famille": "MP", "prix": Decimal("38.50"), "seuil": 15, "unite": "litre", "sous_famille": "Peinture"},
    {"nom": "Vernis brillant 2.5L", "famille": "MP", "prix": Decimal("38.50"), "seuil": 15, "unite": "litre", "sous_famille": "Peinture"},
    {"nom": "Peinture blanche 5L", "famille": "MP", "prix": Decimal("55.00"), "seuil": 12, "unite": "litre", "sous_famille": "Peinture"},
    {"nom": "Peinture noire 5L", "famille": "MP", "prix": Decimal("55.00"), "seuil": 10, "unite": "litre", "sous_famille": "Peinture"},
    {"nom": "Papier verre grain 80", "famille": "MP", "prix": Decimal("0.60"), "seuil": 300, "unite": "pièce", "sous_famille": "Abrasifs"},
    {"nom": "Papier verre grain 120", "famille": "MP", "prix": Decimal("0.65"), "seuil": 300, "unite": "pièce", "sous_famille": "Abrasifs"},
    {"nom": "Papier verre grain 240", "famille": "MP", "prix": Decimal("0.70"), "seuil": 250, "unite": "pièce", "sous_famille": "Abrasifs"},
    {"nom": "Disque à poncer grain 80", "famille": "MP", "prix": Decimal("1.20"), "seuil": 100, "unite": "pièce", "sous_famille": "Abrasifs"},
    {"nom": "Scie circulaire lame 190mm", "famille": "MP", "prix": Decimal("45.00"), "seuil": 8, "unite": "pièce", "sous_famille": "Outillage"},
    {"nom": "Scie sauteuse lame bois", "famille": "MP", "prix": Decimal("8.50"), "seuil": 20, "unite": "pièce", "sous_famille": "Outillage"},
    
    # Produits Finis (PF)
    {"nom": "Table basse chêne 80cm", "famille": "PF", "prix": Decimal("89.00"), "seuil": 5, "unite": "pièce", "sous_famille": "Tables"},
    {"nom": "Table basse noyer 90cm", "famille": "PF", "prix": Decimal("99.00"), "seuil": 4, "unite": "pièce", "sous_famille": "Tables"},
    {"nom": "Table à manger 6 places", "famille": "PF", "prix": Decimal("299.00"), "seuil": 2, "unite": "pièce", "sous_famille": "Tables"},
    {"nom": "Chaise design bois massif", "famille": "PF", "prix": Decimal("125.00"), "seuil": 3, "unite": "pièce", "sous_famille": "Assise"},
    {"nom": "Chaise scandinave", "famille": "PF", "prix": Decimal("89.00"), "seuil": 4, "unite": "pièce", "sous_famille": "Assise"},
    {"nom": "Tabouret haut 65cm", "famille": "PF", "prix": Decimal("59.00"), "seuil": 6, "unite": "pièce", "sous_famille": "Assise"},
    {"nom": "Armoire 2 portes 180cm", "famille": "PF", "prix": Decimal("450.00"), "seuil": 2, "unite": "pièce", "sous_famille": "Rangement"},
    {"nom": "Buffet 3 tiroirs", "famille": "PF", "prix": Decimal("350.00"), "seuil": 2, "unite": "pièce", "sous_famille": "Rangement"},
    {"nom": "Étagère murale 60cm", "famille": "PF", "prix": Decimal("45.00"), "seuil": 8, "unite": "pièce", "sous_famille": "Rangement"},
    {"nom": "Étagère murale 100cm", "famille": "PF", "prix": Decimal("65.00"), "seuil": 6, "unite": "pièce", "sous_famille": "Rangement"},
    {"nom": "Bureau d'angle", "famille": "PF", "prix": Decimal("199.00"), "seuil": 3, "unite": "pièce", "sous_famille": "Mobilier"},
    {"nom": "Console entrée", "famille": "PF", "prix": Decimal("149.00"), "seuil": 4, "unite": "pièce", "sous_famille": "Mobilier"},
    
    # Consommables
    {"nom": "Gants nitrile M", "famille": "consommable", "prix": Decimal("12.50"), "seuil": 30, "unite": "boîte", "sous_famille": "Protection"},
    {"nom": "Gants nitrile L", "famille": "consommable", "prix": Decimal("12.50"), "seuil": 30, "unite": "boîte", "sous_famille": "Protection"},
    {"nom": "Masques FFP2", "famille": "consommable", "prix": Decimal("22.00"), "seuil": 25, "unite": "boîte", "sous_famille": "Protection"},
    {"nom": "Lunettes de protection", "famille": "consommable", "prix": Decimal("8.00"), "seuil": 40, "unite": "pièce", "sous_famille": "Protection"},
    {"nom": "Chiffons industriels", "famille": "consommable", "prix": Decimal("15.00"), "seuil": 20, "unite": "kg", "sous_famille": "Nettoyage"},
    {"nom": "Nettoyant universel 5L", "famille": "consommable", "prix": Decimal("25.00"), "seuil": 10, "unite": "litre", "sous_famille": "Nettoyage"},
    
    # Produits de recherche
    {"nom": "Lot de réactifs test", "famille": "P.RECH", "prix": Decimal("150.00"), "seuil": 4, "unite": "boîte", "sous_famille": "Réactifs"},
    {"nom": "Solvant nettoyant labo", "famille": "P.RECH", "prix": Decimal("28.00"), "seuil": 10, "unite": "litre", "sous_famille": "Solvants"},
]

# Fournisseurs data
FOURNISSEURS_DATA = [
    {"nom": "Boiserie du Maroc", "code": "BM001", "email": "contact@boiserie.ma", "telephone": "0522123456", "ville": "Casablanca", "categorie": "matieres_premieres", "note": 5, "delai_livraison_moyen": 5, "taux_qualite": 98.5},
    {"nom": "Outillage Pro SARL", "code": "OP002", "email": "sales@outillage.ma", "telephone": "0522987654", "ville": "Tanger", "categorie": "equipements", "note": 4, "delai_livraison_moyen": 3, "taux_qualite": 95.0},
    {"nom": "Emballages Express", "code": "EE003", "email": "info@emballages.ma", "telephone": "0522778899", "ville": "Rabat", "categorie": "emballages", "note": 3, "delai_livraison_moyen": 7, "taux_qualite": 92.0},
    {"nom": "Peintures Modernes", "code": "PM004", "email": "commandes@peintures.ma", "telephone": "0522334455", "ville": "Casablanca", "categorie": "matieres_premieres", "note": 4, "delai_livraison_moyen": 4, "taux_qualite": 96.0},
    {"nom": "Quincaillerie Centrale", "code": "QC005", "email": "contact@quincaillerie.ma", "telephone": "0522556677", "ville": "Fès", "categorie": "matieres_premieres", "note": 4, "delai_livraison_moyen": 6, "taux_qualite": 94.0},
    {"nom": "Mobilier Design", "code": "MD006", "email": "info@mobilierdesign.ma", "telephone": "0522889900", "ville": "Marrakech", "categorie": "services", "note": 5, "delai_livraison_moyen": 10, "taux_qualite": 99.0},
    {"nom": "Consommables Pro", "code": "CP007", "email": "ventes@consommables.ma", "telephone": "0522445566", "ville": "Casablanca", "categorie": "autres", "note": 3, "delai_livraison_moyen": 5, "taux_qualite": 90.0},
    {"nom": "Labo Equipements", "code": "LE008", "email": "service@labo.ma", "telephone": "0522667788", "ville": "Rabat", "categorie": "equipements", "note": 4, "delai_livraison_moyen": 8, "taux_qualite": 97.0},
]

USERS_DATA = [
    {"username": "admin", "first_name": "Admin", "last_name": "System", "email": "admin@stock.com", "phone": "0612345678", "role": "Responsable_magasin", "password": "admin123"},
    {"username": "magasinier1", "first_name": "Jean", "last_name": "Dupont", "email": "jean.dupont@stock.com", "phone": "0623456789", "role": "magasinier", "password": "magasinier123"},
    {"username": "magasinier2", "first_name": "Marie", "last_name": "Martin", "email": "marie.martin@stock.com", "phone": "0634567890", "role": "magasinier", "password": "magasinier123"},
    {"username": "magasinier3", "first_name": "Karim", "last_name": "Benali", "email": "karim.benali@stock.com", "phone": "0645678901", "role": "magasinier", "password": "magasinier123"},
    {"username": "auditeur1", "first_name": "Pierre", "last_name": "Durand", "email": "pierre.durand@stock.com", "phone": "0656789012", "role": "Responsable_Audit", "password": "audit123"},
    {"username": "responsable1", "first_name": "Sophie", "last_name": "Leroy", "email": "sophie.leroy@stock.com", "phone": "0667890123", "role": "Responsable_magasin", "password": "resp123"},
]

# ============= FONCTIONS DE SEEDING =============

def clear_database():
    """⚠️ Supprime toutes les données existantes"""
    print("\n⚠️  Attention: Suppression des données existantes...")
    confirm = input("Tapez 'oui' pour confirmer la suppression: ")
    if confirm.lower() == 'oui':
        print("🗑️  Suppression en cours...")
        CommandeFournisseur.objects.all().delete()
        Fournisseur.objects.all().delete()
        Comptage.objects.all().delete()
        Depreciation.objects.all().delete()
        Mouvement_Sortie_externe.objects.all().delete()
        Mouvement_Sortie.objects.all().delete()
        Mouvement_Entree.objects.all().delete()
        Inventaire.objects.all().delete()
        Emplacement.objects.all().delete()
        Lot.objects.all().delete()
        Article.objects.all().delete()
        Utilisateur.objects.exclude(is_superuser=True).delete()
        HistoriqueAction.objects.all().delete()
        Historique_Classification_ABC.objects.all().delete()
        print("✅ Base de données nettoyée")
        return True
    else:
        print("❌ Suppression annulée")
        return False

def create_users():
    """Création des utilisateurs"""
    print("\n👥 Création des utilisateurs...")
    users = []
    for data in USERS_DATA:
        user, created = Utilisateur.objects.get_or_create(
            username=data['username'],
            defaults={
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'email': data['email'],
                'telephone': data['phone'],
                'role': data['role'],
                'password': make_password(data['password']),
                'is_active': True,
            }
        )
        status = "✅" if created else "⏭️"
        print(f"  {status} {data['username']} ({data['role']})")
        users.append(user)
    return users

def create_fournisseurs():
    """Création des fournisseurs"""
    print("\n🏭 Création des fournisseurs...")
    fournisseurs = []
    for data in FOURNISSEURS_DATA:
        fournisseur, created = Fournisseur.objects.get_or_create(
            code=data['code'],
            defaults={
                'nom': data['nom'],
                'email': data['email'],
                'telephone': data['telephone'],
                'ville': data['ville'],
                'categorie': data['categorie'],
                'note': data['note'],
                'delai_livraison_moyen': data['delai_livraison_moyen'],
                'taux_qualite': data['taux_qualite'],
                'adresse': f"{data['ville']}, Maroc",
                'pays': 'Maroc',
                'est_actif': True,
            }
        )
        status = "✅" if created else "⏭️"
        print(f"  {status} {data['nom']} ({data['code']})")
        fournisseurs.append(fournisseur)
    
    # Create commandes for fournisseurs
    for fournisseur in fournisseurs:
        nb_commandes = random.randint(3, 10)
        for _ in range(nb_commandes):
            date_commande = date.today() - timedelta(days=random.randint(0, 365))
            montant = Decimal(random.randint(5000, 150000))
            statut = random.choice(['recue', 'recue', 'recue', 'confirmee', 'en_livraison'])
            CommandeFournisseur.objects.create(
                fournisseur=fournisseur,
                date_commande=date_commande,
                date_livraison_prevue=date_commande + timedelta(days=fournisseur.delai_livraison_moyen),
                date_livraison_reelle=date_commande + timedelta(days=random.randint(fournisseur.delai_livraison_moyen-2, fournisseur.delai_livraison_moyen+2)) if statut == 'recue' else None,
                montant_total=montant,
                statut=statut,
            )
    print(f"  ✅ {Fournisseur.objects.count()} fournisseurs créés")
    print(f"  ✅ {CommandeFournisseur.objects.count()} commandes créées")
    return fournisseurs

def create_articles():
    """Création des articles"""
    print("\n📦 Création des articles...")
    articles = []
    for data in ARTICLES_DATA:
        # Calcul de la classe ABC
        valeur_estimee = data['prix'] * 200
        if valeur_estimee > 15000:
            classe = 'A'
        elif valeur_estimee > 3000:
            classe = 'B'
        else:
            classe = 'C'
        
        # Date de péremption aléatoire
        if data['famille'] in ['P.RECH', 'consommable']:
            peremption = date.today() + timedelta(days=random.randint(30, 365))
        else:
            peremption = None if random.random() > 0.3 else date.today() + timedelta(days=random.randint(180, 1095))
        
        article, created = Article.objects.get_or_create(
            nom_article=data['nom'],
            defaults={
                'description': f"Description détaillée de {data['nom']}. Qualité professionnelle.",
                'famille': data['famille'],
                'sous_famille': data['sous_famille'],
                'categorie': f"Catégorie {data['famille']}",
                'unite_mesure': data['unite'],
                'prix_unitaire': data['prix'],
                'date_peremption': peremption,
                'statut': random.choice(STATUTS_ARTICLE),
                'seuil_securite': data['seuil'],
                'classe_abc': classe,
                'methode_valorisation': random.choice(['FIFO', 'LIFO', 'CMP']),
            }
        )
        status = "✅" if created else "⏭️"
        print(f"  {status} {data['nom'][:35]}... (Classe {classe})")
        articles.append(article)
    return articles

def create_lots(articles):
    """Création des lots pour chaque article"""
    print("\n🏷️  Création des lots...")
    lots = []
    
    for article in articles:
        nb_lots = random.randint(2, 5)
        for i in range(nb_lots):
            qty_lot = random.randint(20, 500)
            proche = random.choice(PROCHE_VALUES)
            date_entree = date.today() - timedelta(days=random.randint(0, 365))
            
            # Date de péremption
            if article.famille in ['P.RECH', 'consommable']:
                peremption = date_entree + timedelta(days=random.randint(30, 180))
            elif article.date_peremption:
                peremption = article.date_peremption
            else:
                peremption = date_entree + timedelta(days=random.randint(365, 1095))
            
            quantite_restante = random.randint(0, qty_lot)
            cout_unitaire = article.prix_unitaire * Decimal(random.uniform(0.8, 1.1))
            
            lot = Lot.objects.create(
                id_article=article,
                date_peremption=peremption,
                statut=random.choice(STATUTS_LOT),
                proche=proche,
                quantite_lot=qty_lot,
                cout_unitaire=cout_unitaire,
                date_entree=date_entree,
                quantite_restante=quantite_restante,
            )
            lots.append(lot)
    
    print(f"  ✅ {len(lots)} lots créés")
    return lots

def generate_coordinates(zone, rack, etagere):
    """Génère des coordonnées réalistes"""
    base = ZONE_COORDS.get(zone, ZONE_COORDS['stockage'])
    rack_offset = (rack * 0.0003) % base['range']
    etagere_offset = (ord(str(etagere)[0]) % 10) * 0.0001 if str(etagere) else 0.0001
    random_offset = random.uniform(-0.0005, 0.0005)
    lat = base['lat'] + rack_offset + etagere_offset + random_offset
    lng = base['lng'] + rack_offset + etagere_offset + random_offset
    lat = max(base['lat'] - base['range'], min(base['lat'] + base['range'], lat))
    lng = max(base['lng'] - base['range'], min(base['lng'] + base['range'], lng))
    return round(lat, 7), round(lng, 7)

def create_emplacements(articles, lots):
    """Création des emplacements avec coordonnées"""
    print("\n📍 Création des emplacements...")
    emplacements = []
    
    rack_count = 1
    for zone in ZONES:
        for rack in range(1, 13):  # 12 racks par zone
            for etagere in ['A', 'B', 'C', 'D', 'E']:  # 5 étagères par rack
                if zone == 'stockage':
                    capacite_max = random.choice([150, 200, 250])
                elif zone == 'préparation':
                    capacite_max = random.choice([80, 100, 120])
                else:
                    capacite_max = random.choice([50, 75, 100])
                
                assign_article = random.random() < 0.6
                article = random.choice(articles) if assign_article and articles else None
                capacite_actuelle = random.randint(0, capacite_max) if assign_article else 0
                lat, lng = generate_coordinates(zone, rack, etagere)
                
                emplacement, created = Emplacement.objects.get_or_create(
                    zone_physique=zone,
                    rack=rack,
                    etagere=etagere,
                    defaults={
                        'capacite_max': capacite_max,
                        'capacite_actuelle': capacite_actuelle,
                        'id_article': article,
                        'latitude': lat,
                        'longitude': lng,
                    }
                )
                if created:
                    emplacements.append(emplacement)
    
    print(f"  ✅ {len(emplacements)} emplacements créés")
    return emplacements

def create_mouvements(articles, lots):
    """Création des mouvements d'entrée et de sortie"""
    print("\n📥 Création des mouvements...")
    
    # Mouvements d'entrée
    entrees = []
    for lot in lots:
        mouvement = Mouvement_Entree.objects.create(
            id_article=lot.id_article,
            id_lot=lot,
            date_entree=lot.date_entree,
            type_entree=random.choice(TYPE_ENTREE),
            documents_reglementaires=f"DOC_{random.randint(10000, 99999)}" if random.random() > 0.7 else None,
        )
        entrees.append(mouvement)
    
    print(f"  ✅ {len(entrees)} mouvements d'entrée créés")
    
    # Mouvements de sortie internes
    sorties_internes = []
    for _ in range(200):
        lot = random.choice(lots)
        if lot.quantite_restante > 0:
            qty = min(random.randint(1, 30), lot.quantite_restante)
            date_sortie = lot.date_entree + timedelta(days=random.randint(1, 180))
            if date_sortie <= date.today():
                sortie = Mouvement_Sortie.objects.create(
                    id_article=lot.id_article,
                    id_lot=lot,
                    date_sortie=date_sortie,
                    quantite_sortie=qty,
                    type_sortie=random.choice(TYPE_SORTIE_INTERNE),
                    valeur_sortie=qty * lot.cout_unitaire,
                )
                sorties_internes.append(sortie)
    
    print(f"  ✅ {len(sorties_internes)} sorties internes créées")
    
    # Mouvements de sortie externes
    sorties_externes = []
    for _ in range(150):
        lot = random.choice(lots)
        if lot.quantite_restante > 0:
            qty = min(random.randint(1, 20), lot.quantite_restante)
            date_sortie = lot.date_entree + timedelta(days=random.randint(1, 150))
            if date_sortie <= date.today():
                sortie = Mouvement_Sortie_externe.objects.create(
                    id_article=lot.id_article,
                    id_lot=lot,
                    date_sortie=date_sortie,
                    quantite_sortie=qty,
                    type_sortie=random.choice(TYPE_SORTIE_EXTERNE),
                    documents_reglementaires=f"EXT_{random.randint(10000, 99999)}" if random.random() > 0.7 else None,
                    valeur_sortie=qty * lot.cout_unitaire * Decimal('1.3'),
                )
                sorties_externes.append(sortie)
    
    print(f"  ✅ {len(sorties_externes)} sorties externes créées")
    return entrees, sorties_internes, sorties_externes

def create_inventaires(articles, users):
    """Création des inventaires (NOUVEAU MODÈLE)"""
    print("\n📋 Création des inventaires (écarts)...")
    
    # Récupérer un utilisateur responsable
    responsable = users[0] if users else None
    for user in users:
        if user.role == 'Responsable_magasin':
            responsable = user
            break
    
    if not responsable:
        print("  ⚠️ Aucun responsable trouvé")
        return []
    
    inventaires = []
    
    # Créer 15-25 inventaires aléatoires
    nb_inventaires = random.randint(15, 25)
    
    # Liste des statuts possibles (sans weights)
    statuts_possibles = ['valide', 'valide', 'valide', 'valide', 'valide', 'valide', 'valide', 'brouillon', 'brouillon', 'corrige']
    
    for i in range(nb_inventaires):
        # Choisir un article aléatoire
        article = random.choice(articles)
        
        # Calculer la quantité théorique
        quantite_theorique = article.quantite_stock_actuel()
        
        # Générer un écart réaliste (entre -20 et +20)
        ecart = random.randint(-20, 20)
        quantite_reelle = max(0, quantite_theorique + ecart)
        
        # Date aléatoire dans les 90 derniers jours
        date_inventaire = date.today() - timedelta(days=random.randint(0, 90))
        
        # Choisir un statut aléatoire avec distribution approximative
        statut = random.choice(statuts_possibles)
        
        # Notes aléatoires
        notes_options = [
            "Inventaire mensuel",
            "Comptage physique effectué",
            "Écart détecté - vérification manuelle",
            "Stock corrigé après comptage",
            "Produits bien rangés",
            "Écart constaté - à investiguer",
            "Comptage OK",
        ]
        notes = random.choice(notes_options)
        
        # Ajouter l'écart aux notes si présent
        if ecart != 0:
            notes += f" (Écart: {ecart} {article.unite_mesure})"
        
        inventaire = Inventaire.objects.create(
            article=article,
            quantite_theorique=quantite_theorique,
            quantite_reelle=quantite_reelle,
            date_inventaire=date_inventaire,
            responsable=responsable,
            notes=notes,
            statut=statut
        )
        inventaires.append(inventaire)
    
    print(f"  ✅ {len(inventaires)} inventaires créés")
    
    # Afficher quelques statistiques
    ecarts_positifs = sum(1 for i in inventaires if i.ecart > 0)
    ecarts_negatifs = sum(1 for i in inventaires if i.ecart < 0)
    ecarts_nuls = sum(1 for i in inventaires if i.ecart == 0)
    
    print(f"     📊 Écarts: +{ecarts_positifs} / -{ecarts_negatifs} / ={ecarts_nuls}")
    
    return inventaires

def create_depreciations(articles, lots):
    """Création des dépréciations"""
    print("\n💰 Création des dépréciations...")
    
    depreciations = []
    lots_valides = [lot for lot in lots if lot.quantite_restante > 0]
    if lots_valides:
        nb_depreciations = min(15, len(lots_valides))
        lots_a_deprecier = random.sample(lots_valides, nb_depreciations)
        
        for lot in lots_a_deprecier:
            montant = lot.cout_unitaire * Decimal('0.15') * lot.quantite_restante
            depreciation = Depreciation.objects.create(
                id_article=lot.id_article,
                id_lot=lot,
                date_depreciation=date.today() - timedelta(days=random.randint(1, 180)),
                montant_depreciation=montant,
                cout=lot.cout_unitaire,
            )
            depreciations.append(depreciation)
    
    print(f"  ✅ {len(depreciations)} dépréciations créées")
    return depreciations

def create_abc_history(articles):
    """Création de l'historique des classifications ABC"""
    print("\n📊 Création de l'historique ABC...")
    
    histories = []
    for article in articles:
        nb_changes = random.randint(0, 2)
        current_class = article.classe_abc
        for _ in range(nb_changes):
            new_class = random.choice(['A', 'B', 'C'])
            while new_class == current_class:
                new_class = random.choice(['A', 'B', 'C'])
            date_changement = date.today() - timedelta(days=random.randint(30, 365))
            history = Historique_Classification_ABC.objects.create(
                id_article=article,
                ancienne_classe=current_class,
                nouvelle_classe=new_class,
                date_changement=date_changement
            )
            histories.append(history)
            current_class = new_class
    
    print(f"  ✅ {len(histories)} entrées d'historique ABC créées")
    return histories

def show_statistics(users, articles, lots, emplacements, fournisseurs, inventaires):
    """Affiche les statistiques"""
    print("\n" + "="*60)
    print("📊 STATISTIQUES DE LA BASE DE DONNÉES")
    print("="*60)
    print(f"👥 Utilisateurs: {len(users)}")
    print(f"🏭 Fournisseurs: {len(fournisseurs)}")
    print(f"📦 Articles: {len(articles)}")
    print(f"🏷️ Lots: {len(lots)}")
    print(f"📍 Emplacements: {len(emplacements)}")
    print(f"   - Avec coordonnées: {Emplacement.objects.filter(latitude__isnull=False).count()}")
    print(f"📥 Mouvements entrée: {Mouvement_Entree.objects.count()}")
    print(f"📤 Mouvements sortie internes: {Mouvement_Sortie.objects.count()}")
    print(f"📤 Mouvements sortie externes: {Mouvement_Sortie_externe.objects.count()}")
    print(f"📋 Inventaires (écarts): {len(inventaires)}")
    print(f"💰 Dépréciations: {Depreciation.objects.count()}")
    print(f"📊 Historique ABC: {Historique_Classification_ABC.objects.count()}")
    print(f"💸 Commandes fournisseurs: {CommandeFournisseur.objects.count()}")
    
    total_quantite = sum(a.quantite_stock_actuel() for a in articles)
    total_valeur = sum(a.valeur_stock_actuel() for a in articles)
    print(f"\n💾 Stock total: {total_quantite} unités")
    print(f"💰 Valeur totale stock: {total_valeur:.2f} DH")
    
    # Statistiques des écarts d'inventaire
    if inventaires:
        ecart_total = sum(i.ecart for i in inventaires)
        articles_conformes = sum(1 for i in inventaires if i.ecart == 0)
        print(f"\n📊 Écarts d'inventaire:")
        print(f"   - Écart total: {ecart_total} unités")
        print(f"   - Articles conformes: {articles_conformes}/{len(inventaires)} ({articles_conformes/len(inventaires)*100:.1f}%)")
    
    articles_critiques = [a for a in articles if 0 < a.quantite_stock_actuel() < a.seuil_securite]
    articles_rupture = [a for a in articles if a.quantite_stock_actuel() <= 0]
    print(f"\n⚠️ Alertes stock:")
    print(f"   - Stock critique: {len(articles_critiques)} articles")
    print(f"   - Rupture: {len(articles_rupture)} articles")
    
    today = date.today()
    perimes = [a for a in articles if a.date_peremption and a.date_peremption < today]
    print(f"\n⏰ Périmptions:")
    print(f"   - Produits périmés: {len(perimes)} articles")
    
    emplacements_occupes = Emplacement.objects.filter(id_article__isnull=False).count()
    print(f"\n📍 Occupation emplacements: {emplacements_occupes}/{len(emplacements)} ({emplacements_occupes/len(emplacements)*100:.1f}%)")

@transaction.atomic
def seed_all():
    """Fonction principale"""
    print("🚀 DÉBUT DU SEEDING DE LA BASE DE DONNÉES")
    print("="*60)
    
    try:
        users = create_users()
        fournisseurs = create_fournisseurs()
        articles = create_articles()
        lots = create_lots(articles)
        emplacements = create_emplacements(articles, lots)
        create_mouvements(articles, lots)
        inventaires = create_inventaires(articles, users)
        create_depreciations(articles, lots)
        create_abc_history(articles)
        
        show_statistics(users, articles, lots, emplacements, fournisseurs, inventaires)
        
        print("\n" + "="*60)
        print("✅ SEEDING TERMINÉ AVEC SUCCÈS !")
        print("="*60)
        
        print("\n📍 Exemple de coordonnées générées:")
        for emp in Emplacement.objects.filter(latitude__isnull=False)[:5]:
            print(f"   - {emp.zone_physique} - Rack {emp.rack} - E{emp.etagere}: ({emp.latitude}, {emp.longitude})")
        
        print("\n📊 Exemple d'écarts d'inventaire:")
        for inv in inventaires[:5]:
            print(f"   - {inv.article.nom_article}: théo={inv.quantite_theorique}, réel={inv.quantite_reelle}, écart={inv.ecart}")
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Seed la base de données')
    parser.add_argument('--clear', action='store_true', help='Efface les données avant de seed')
    args = parser.parse_args()
    
    if args.clear:
        if clear_database():
            seed_all()
    else:
        seed_all()