# Knowledge Network Builder

A Flask-based web application for building and visualizing knowledge networks from academic documents, with a focus on Islamic jurisprudence (fiqh) texts.

## Features

### 📚 Document Management
- Upload PDF documents with metadata extraction
- BibTeX parsing with support for Turkish characters and LaTeX encoding
- Automatic categorization by doctrine and subject
- Individual document management for administrators

### 🧠 AI-Powered Knowledge Extraction
- Integration with Google Gemini AI for content analysis
- Automatic extraction of keywords, questions, and answers
- Intelligent text processing with citation tracking
- Support for Turkish academic texts

### 🌐 Interactive Network Visualization
- Global knowledge network using Sigma.js
- Four-level hierarchy: Categories → Keywords → Questions → Books
- Real-time filtering by category and doctrine
- Advanced search capabilities with node highlighting

### 🔍 Advanced Analysis Tools
- **Question Path Finder**: Discover intellectual connections between concepts
- **Consistency Checker**: Analyze contradictions between authors using AI
- **Narrative Analysis**: Generate scholarly discourse narratives tracing idea development
- Multi-path exploration with detailed visualization

### 👥 User Management
- Role-based access control (Admin, Premium, Free users)
- API usage tracking with daily limits
- Automated daily reset system
- Individual document permissions

### 🎯 Smart Features
- Caching system for consistency checks to reduce API calls
- Unicode support for Turkish characters
- Robust error handling and logging
- Progressive processing for large documents

## Installation

### Prerequisites
- Python 3.8+
- Google Gemini API key
- Modern web browser

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/knowledge-network-builder.git
cd knowledge-network-builder
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
SECRET_KEY=your_secret_key_here
```

4. **Initialize the database**
```bash
python run.py
```

5. **Access the application**
Open your browser and navigate to `http://127.0.0.1:5000`

## Usage

### For Regular Users
1. **Upload Documents**: Add PDF files with metadata
2. **Process Content**: Let AI extract knowledge structures
3. **Explore Networks**: Navigate the interactive visualization
4. **Find Connections**: Use the path finder to discover intellectual links
5. **Analyze Discourse**: Generate narrative analyses of scholarly conversations

### For Administrators
1. **User Management**: Control user roles and permissions
2. **Document Oversight**: Manage all users' documents
3. **API Monitoring**: Track usage patterns and limits
4. **System Analytics**: Monitor application performance

## Project Structure

```
knowledge-network-builder/
├── app/                    # Main application package
│   ├── routes/            # Flask route blueprints
│   ├── services/          # Business logic services
│   ├── utils/             # Utility functions
│   └── models/            # Database models
├── templates/             # Jinja2 HTML templates
├── static/               # CSS, JavaScript, and assets
├── uploads/              # User-uploaded files
├── schema.sql            # Database schema
├── requirements.txt      # Python dependencies
└── run.py               # Application entry point
```

## Key Components

### Backend
- **Flask**: Web framework with blueprint architecture
- **SQLite**: Database with optimized schema
- **Google Gemini AI**: Content analysis and narrative generation
- **PyPDF2**: PDF text extraction
- **Unicode Support**: Full Turkish character compatibility

### Frontend
- **Sigma.js**: Interactive network visualization
- **Responsive Design**: Mobile-friendly interface
- **Real-time Updates**: Dynamic content loading
- **Advanced UI**: Modals, filters, and progressive disclosure

## API Endpoints

### Network Visualization
- `GET /api/global_network_data` - Retrieve network graph data
- `POST /api/find-question-path` - Find paths between concepts

### Analysis Tools
- `POST /api/check-consistency` - Analyze answer consistency
- `POST /api/narrative-analysis` - Generate discourse narratives

### Document Management
- `POST /upload` - Upload and process documents
- `POST /admin/api/admin/delete-document` - Administrative deletion

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Technical Highlights

### AI Integration
- Smart prompt engineering for knowledge extraction
- Caching system to optimize API usage
- Error handling for API timeouts and limits

### Network Analysis
- Breadth-first search algorithms for path finding
- Multi-level filtering with real-time updates
- Intelligent node highlighting and selection

### Data Processing
- Robust BibTeX parser with nested brace support
- LaTeX to Unicode conversion for Turkish texts
- Progressive document processing with status tracking

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Google Gemini AI for content analysis capabilities
- Sigma.js community for network visualization tools
- Flask community for the robust web framework
- Academic researchers whose work this tool supports

## Support

For questions, issues, or contributions, please open an issue on GitHub or contact the development team.

---

**Knowledge Network Builder** - Transforming academic documents into interactive knowledge graphs for deeper understanding and discovery.