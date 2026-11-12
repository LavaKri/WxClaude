# Aide de WxClaude

WxClaude est une interface de bureau pour la ligne de commande Claude Code, utilisée en mode non interactif (`claude -p`).
Elle est conçue pour un usage avec lecteur d'écran et au clavier seul.
Elle utilise les contrôles natifs de Windows.
Ce n'est pas un terminal.

## Installation et configuration

### Claude Code (claude -p)

WxClaude a besoin du programme Claude Code.
Installez-le en suivant la [documentation de Claude Code](https://code.claude.com/docs/en/overview).

Vérifiez l'installation dans un terminal avec `claude --version`.

Pour utiliser Claude Code, il est obligatoire de s'authentifier :

- dans un terminal, lancez `claude auth login` et suivez les instructions ;
- vérifiez avec `claude auth status`.

### Claude dans WxClaude

Dans l'onglet "Claude" des préférences, il sera possible de définir l'utilisation du programme Claude Code.

Notamment, le type d'interface est la façon dont les questions de permission de Claude parviennent à WxClaude.
Il s'applique au message suivant et peut être changé à tout moment.

- **Protocole stdio** (par défaut) :
toutes les questions de permission, les questions structurées de Claude et l'approbation de ses plans.
- **Hook HTTP** :
les questions de permission sur les outils. WxClaude démarre pour cela un serveur HTTP local sur 127.0.0.1.

Avec le hook HTTP, une question sans réponse dans le délai d'attente est refusée par Claude Code. Réglez ce délai (1 à 10 minutes) sur la même page.

Dans le mode de permission *Ne pas demander*, rien n'est demandé, quel que soit le type.

## Fonctionnement

### Espaces de travail

Un espace de travail est simplement le dossier où Claude va travailler.
Ainsi, il est important de lui fixer des limites dans cet espace.
Pour cela, les Paramètres de l'espace de travail permettent de définir des règles de permission et des variables d'environnement.
Tous ces paramètres sont nativement partagés avec l'application Claude Code.

Toutefois, ces paramètres pourraient être modifiés sans réel avertissement, par exemple à la suite d'une opération Git, d'un écrasement, etc.
C'est pourquoi ces fichiers de paramètres sont sous surveillance, pour pouvoir indiquer tous les changements extérieurs à WxClaude.
En cas de doute, l'application pourra fonctionner en mode restreint, c'est-à-dire que les agents seront limités dans leurs actions.
Pour retrouver un fonctionnement normal, il suffira d'approuver le dossier dans les paramètres de l'espace de travail.

- Fichier > Ouvrir depuis les projets Claude liste les dossiers déjà utilisés avec Claude Code.
- Au démarrage, le dernier espace de travail est rouvert. Vous pouvez le désactiver dans les Préférences, page Général.

### Conversations

Une conversation appartient toujours à un espace de travail. Ouvrir un espace de travail charge sa conversation mémorisée, sinon la plus récente. Une conversation n'est jamais créée automatiquement.

- Conversation > Reprendre une conversation liste celles de l'espace de travail, la plus récente d'abord.
- Conversation > Actualiser la conversation relit le fichier de session.
- Conversation > Nouvelle branche de conversation copie la conversation sous un autre nom. Le texte reste affiché. La copie est faite par Claude Code avec le premier message de la branche ; la conversation d'origine ne change pas.
- Conversation > Supprimer la conversation met à la Corbeille de Windows ce que Claude Code garde de la conversation, après confirmation. Vous pouvez la récupérer depuis la Corbeille.
- Conversation > Modifier l'agent change l'agent de la conversation courante.
Changer de modèle fait perdre le cache de l'invite de la conversation. Changer l'effort ou le mode de permission ne le fait pas.

### Agents

Un agent est un ensemble de caractéristiques, propre à un fournisseur.
Pour WxClaude, il se limite à un modèle, un effort et un mode de permission.
- Chaque conversation a son propre agent principal.
Configurable, indépendamment des autres conversations, dans une boîte de dialogue dédiée.
- Chaque espace de travail a son propre agent alternatif.
Configurable dans les paramètres de l'espace de travail.
Utile pour, par exemple, envoyer rapidement des messages avec un niveau d'effort faible, sans avoir à modifier l'agent principal de la conversation.

Dans les préférences, on peut définir :
- l'agent principal, par défaut pour une nouvelle conversation.
- l'agent alternatif, par défaut pour un nouvel espace de travail.

### Permissions

Quand Claude veut utiliser un outil que le mode de permission n'autorise pas, une boîte de dialogue pose la question. La barre d'état l'annonce.

- *Autoriser* autorise l'outil cette fois.
- *Toujours autoriser* écrit une règle dans `.claude/settings.local.json`, comme le fait Claude Code. Ce bouton apparaît quand Claude Code propose une règle.
- *Refuser* refuse. Vous pouvez saisir une explication envoyée à Claude.

Fermer la boîte avec Échap est un refus. Le premier champ décrit la demande et reçoit le focus initial.

Les paramètres de l'espace de travail permettent de donner à chaque outil une règle d'autorisation, de demande ou de refus. Le refus l'emporte sur la demande, et la demande sur l'autorisation.

## Interface utilisateur

### Zone de conversation

La zone de conversation affiche l'échange en lecture seule.
Vos prompts (messages) sont sous un titre de niveau 1.
Les réponses de Claude sont sous un titre de niveau 2.
Les raccourcis clavier classiques de navigation web sont utilisables (titre, liste, tableau).
Des fenêtres d'affichage adaptées facilitent la lecture de certains éléments (voir le menu contextuel).

### Prompt

Le prompt est le champ où vous écrivez votre message à Claude.
Il peut contenir plusieurs lignes. Son menu contextuel est celui de Windows.
Il est grisé tant qu'il n'y a pas de conversation active.

Deux boutons envoient le message : l'un avec l'agent de la conversation, l'autre avec l'agent alternatif.
Pendant que Claude répond, l'envoi est grisé. Le champ reste utilisable pour de la saisie.

Le bouton *Interrompre Claude* arrête la réponse et les programmes lancés par Claude.
Il n'est actif que pendant une réponse.

### Barre d'état

La barre d'état a trois zones. Elle ne prend pas le focus : utilisez la commande de votre lecteur d'écran pour la lire.

- La position : `Message 3 sur 8` indique le message où se trouve le curseur parmi les vôtres. Elle est vide s'il n'y en a pas.
- L'étape : `Étape 2 sur 5 : sujet` indique la tâche de la liste de Claude qu'il vient de commencer. Elle est vide s'il n'y en a pas et quand WxClaude attend votre message.
- Le message : la dernière annonce.
Quand WxClaude est prêt à recevoir des messages, il l'indique avec les jauges de votre abonnement.

### Annonces

WxClaude dit ce qui se passe à votre lecteur d'écran. Les annonces sont regroupées en catégories.

Dans l'onglet "Annonces" des préférences, vous choisissez pour chaque catégorie ce qui est fait.
Selon la catégorie : rien, un message, la lecture de la ligne, une boîte de dialogue ou un son.
Le choix "Annonces" coupe ou rétablit l'envoi vers le lecteur d'écran.

Les erreurs de Claude ouvrent toujours une boîte de dialogue.
Quel que soit l'état de sortie des annonces, elles sont toutes mémorisées dans un historique, consultable depuis l'aide.

#### Alertes de jauge

L'abonnement de Claude Code a deux jauges : la fenêtre de 5 heures et la semaine.
Chaque alerte est dite la première fois que la jauge atteint ou dépasse son seuil.
Les seuils sont ceux de Claude Code : 90 % pour les 5 heures, 25, 50 et 75 % pour la semaine.

Avec d'autres fournisseurs, les jauges et alertes ne seront pas disponibles.
Seul le solde, ou crédit, pourra être consulté dans la boîte de dialogue de jauge, pour ceux qui le fournissent.

### Tâches, plans et utilisation

Trois fenêtres d'information s'ouvrent à la demande. Elles montrent ce que WxClaude sait au moment de l'ouverture.
- La liste de tâches donne les tâches que Claude s'est fixées pour la conversation : numéro, sujet et état (en attente, en cours, terminée). Une ligne dit aussi ce qui la bloque. Le détail de la tâche choisie est dessous.
- Les plans sont ceux que Claude a écrits dans le mode de permission *Planifier seulement*. Ils sont en lecture seule : il n'y a rien à approuver ici.
- L'utilisation montre les jauges de l'abonnement et leur remise à zéro. Elle donne aussi des informations sur les jetons utilisés.

## Autres fournisseurs d'IA

Un fournisseur est une source de modèles autre que votre abonnement Claude : un service distant (DeepSeek, GLM, OpenRouter) ou un serveur sur votre machine (Ollama, LM Studio).
Seuls les fournisseurs proposant la prise en charge d'Anthropic sont utilisables avec WxClaude. Il devrait être possible d'élargir la liste en utilisant un relais, tel que LiteLLM.

Claude est toujours présent, c'est le choix par défaut, et il ne peut ni se modifier ni se supprimer.
Les fournisseurs sont communs à toute l'application, pas propres à un espace de travail.
L'utilisation de WxClaude avec un fournisseur est possible sans être identifié avec un compte Claude Code.

Dans les préférences, le formulaire d'un fournisseur permet de définir :

- un nom et une adresse (URL) ;
- une clé API, ou « aucune » pour un serveur local ;
- la liste des modèles disponibles et des variables de configuration.

### Protection des clés API

Les clés d'autorisation des fournisseurs sont chiffrées avec votre compte Windows.
Plusieurs méthodes de transmission des clés à Claude Code sont possibles :

- Masquée (par défaut) : les commandes que Claude exécute ne voient pas la clé, mais la CLI impose alors le mode de permission manuel. Les modes Plan, Accepter les modifications, Auto et Ne pas demander ne s'appliquent pas.
- Partagée : tous les modes marchent, mais les commandes de Claude peuvent lire la clé, et une consigne cachée dans un fichier ou une page web pourrait la leur faire révéler.
- Relayée : la clé reste seulement dans WxClaude, derrière un petit relais sur votre ordinateur (`127.0.0.1`). Tous les modes marchent, au prix d'un mécanisme de fonctionnement plus complexe.

### Confidentialité

- Pour un fournisseur autre que Claude, la télémétrie et les envois non essentiels vers Anthropic sont désactivés.
- Aussi, les prompts et les réponses ne transiteront pas par les serveurs d'Anthropic.

### Particularités

- Avec un fournisseur autre que celui d'Anthropic, l'agent répondra toujours au nom de Claude.

## Déléguer des tâches à une IA locale

Pour des raisons économiques ou de confidentialité, il est possible d'utiliser une IA locale avec Claude Code.
Claude reste votre interlocuteur, qui va pouvoir externaliser certaines tâches.
WxClaude ne propose pas de configuration pour ce mode d'utilisation, mais certaines annonces lui sont dédiées.

Procédure simplifiée de mise en œuvre :

- Installer et configurer une IA en local (LM Studio, Ollama, ...).
- Installer et configurer un serveur MCP (MCP in LM Studio, ollama-mcp, ...).
- Déclarer le serveur MCP à Claude Code,
soit avec Claude Code, dans son interface ou en ligne de commande,
soit directement avec les fichiers `.claude.json` ou `.mcp.json`.
- Dans WxClaude, demander à Claude d'utiliser l'IA locale pour certaines tâches.