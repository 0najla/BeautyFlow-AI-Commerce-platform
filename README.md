================================================================================
                                  BEAUTYFLOW
               AI-Powered Collaborative Beauty Import Platform
                    Version: 1.0.0 (Graduation Release)
================================================================================

                           FINAL YEAR PROJECT
                    Al-Baha University – Saudi Arabia
          Department of Computer Information Systems (CIS)

================================================================================
                              PROJECT OVERVIEW
================================================================================

BeautyFlow is an AI-powered collaborative beauty import platform designed to
address the challenges faced by small beauty businesses and individuals in
Saudi Arabia when importing beauty products. The platform enables users to
collaborate on shipping costs, generate AI-powered custom packaging designs,
and receive intelligent product recommendations.

By allowing groups of users to share shipping expenses, BeautyFlow significantly
reduces import costs while enhancing the overall user experience through
artificial intelligence and modern web technologies.

================================================================================
                               KEY FEATURES
================================================================================

1. AI Custom Packaging Design
   - AI-powered image generation using OpenAI GPT-Image-1
   - Step-by-step customization wizard including:
     • Product type
     • Formula base
     • Coverage level
     • Finish type
     • Skin type compatibility
     • Custom packaging description
   - Save generated designs to favorites
   - View design history

2. Cost-Sharing Shipping System
   - Group-based shipping (up to 5 users per group)
   - Automatic shipping cost calculation and division
   - Real-time group status tracking
   - Support for multiple cities within Saudi Arabia
   - Group expiration handling for incomplete groups

3. SmartPicks – AI Product Recommendations
   - AI-based product suggestions based on user style preferences
   - Supports multiple aesthetic styles
   - One-click add-to-cart functionality

4. Mika – AI Chatbot Assistant
   - Powered by OpenAI GPT-4o-mini
   - Bilingual support (English and Arabic)
   - Provides platform guidance and user support

5. User Authentication and Security
   - Secure email and password authentication
   - Two-Factor Authentication (2FA) via SMS
   - Twilio integration for OTP verification
   - Secure password hashing and session handling

6. Shopping Cart and Checkout
   - Persistent shopping cart
   - Real-time price calculation
   - Detailed cost breakdown including taxes and fees
   - Multiple payment methods support

7. Order Management and Tracking
   - View order history and status
   - Shipment tracking
   - Invoice generation and access

8. Regulatory Compliance
   - Support for Saudi Food and Drug Authority (SFDA) requirements
   - Compliance-related documentation handling

================================================================================
                            SYSTEM REQUIREMENTS
================================================================================

Software Requirements:
- Python 3.9 or higher
- PostgreSQL 13 or higher
- Modern web browser
- Internet connection (for AI services)

Required External Services:
- OpenAI API (AI image generation and chatbot)
- Twilio SMS service (OTP verification)

================================================================================
                             INSTALLATION GUIDE
================================================================================

1. Clone or download the project files to your local machine.

2. Create and activate a virtual environment (recommended).

3. Install required Python libraries using pip.

4. Configure the PostgreSQL database and create a new database.

5. Create a `.env` file inside the backend directory and define the required
   environment variables (database connection, secret key, API keys).

   Note:
   Sensitive configuration files such as `.env` are excluded from version
   control for security purposes.

6. Initialize and migrate the database.

7. Run the application using:
   python app.py

8. Access the application via:
   http://localhost:5000

================================================================================
                            PROJECT STRUCTURE
================================================================================

beautyflow/
├── backend/
│   ├── app.py                 Main Flask application
│   ├── models/                Database models
│   ├── migrations/            Database migrations
│   └── .env                   Environment variables (excluded)
│
├── templates/                 HTML templates
├── static/                    CSS, JavaScript, and images
└── README.md                  Project documentation

================================================================================
                            DATABASE TABLES
================================================================================

- accounts
- account_profiles
- account_security
- products
- orders
- order_items
- payments
- wishlists
- wishlist_items
- ai_sessions
- ai_messages
- ai_generations
- notifications
- invoices

================================================================================
                              TEAM MEMBERS
================================================================================

- Najla Abdullah Alzahrani
- Dania Kamel Algamdi
- Maha Zaid Algamdi
- Nora Naseer Algamdi
- Bayan Ali Algamdi

================================================================================
                               SUPERVISOR
================================================================================

Dr. Adil Fahad Alharthi  
Department of Computer Science  
Al-Baha University

================================================================================
                               CONCLUSION
================================================================================

BeautyFlow represents a comprehensive solution for collaborative beauty product
import in Saudi Arabia. By combining artificial intelligence with collaborative
commerce, the platform demonstrates a practical and scalable approach to
reducing costs while enhancing user experience.

The project showcases the integration of:
- Artificial Intelligence
- Secure backend development
- Database-driven system architecture
- User-centered interface design
- E-commerce and payment workflows

================================================================================
                            ACKNOWLEDGMENTS
================================================================================

The project team would like to express sincere appreciation to the project
supervisor, Al-Baha University, and all contributors who supported the
development and evaluation of this system.

================================================================================
                    © 2025 BeautyFlow Team – All Rights Reserved
================================================================================
