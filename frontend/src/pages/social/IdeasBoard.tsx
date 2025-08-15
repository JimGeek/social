import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import socialAPI, { SocialIdea, SocialPlatform } from '../../services/socialApi';

interface IdeasBoardProps {}

interface KanbanColumn {
  id: string;
  title: string;
  status: 'idea' | 'in_progress' | 'scheduled' | 'published' | 'archived';
  color: string;
  ideas: SocialIdea[];
}

const IdeasBoard: React.FC<IdeasBoardProps> = () => {
  const navigate = useNavigate();
  
  // State management
  const [ideas, setIdeas] = useState<SocialIdea[]>([]);
  const [platforms, setPlatforms] = useState<SocialPlatform[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAIModal, setShowAIModal] = useState(false);
  const [selectedIdea, setSelectedIdea] = useState<SocialIdea | null>(null);
  const [draggedIdea, setDraggedIdea] = useState<SocialIdea | null>(null);
  
  // New idea form state
  const [newIdea, setNewIdea] = useState({
    title: '',
    description: '',
    content_draft: '',
    tags: [] as string[],
    category: '',
    target_platforms: [] as string[],
    priority: 1
  });
  
  // AI generation state
  const [aiRequest, setAiRequest] = useState({
    topics: [] as string[],
    business_type: 'construction',
    platform: 'facebook',
    count: 5
  });
  const [isGeneratingAI, setIsGeneratingAI] = useState(false);

  // Kanban columns configuration
  const columns: KanbanColumn[] = [
    {
      id: 'idea',
      title: 'Ideas',
      status: 'idea',
      color: 'bg-gray-100',
      ideas: ideas.filter(idea => idea.status === 'idea')
    },
    {
      id: 'in_progress',
      title: 'In Progress',
      status: 'in_progress',
      color: 'bg-brand-100',
      ideas: ideas.filter(idea => idea.status === 'in_progress')
    },
    {
      id: 'scheduled',
      title: 'Scheduled',
      status: 'scheduled',
      color: 'bg-yellow-100',
      ideas: ideas.filter(idea => idea.status === 'scheduled')
    },
    {
      id: 'published',
      title: 'Published',
      status: 'published',
      color: 'bg-green-100',
      ideas: ideas.filter(idea => idea.status === 'published')
    },
    {
      id: 'archived',
      title: 'Archived',
      status: 'archived',
      color: 'bg-red-100',
      ideas: ideas.filter(idea => idea.status === 'archived')
    }
  ];

  // Load initial data
  useEffect(() => {
    loadIdeasData();
  }, []);

  const loadIdeasData = async () => {
    setIsLoading(true);
    try {
      const [ideasData, platformsData] = await Promise.all([
        socialAPI.getIdeas(),
        socialAPI.getPlatforms()
      ]);
      
      setIdeas(ideasData);
      setPlatforms(platformsData);
    } catch (error) {
      console.error('Failed to load ideas data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Drag and drop handlers
  const handleDragStart = (idea: SocialIdea) => {
    setDraggedIdea(idea);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = async (e: React.DragEvent, targetStatus: string) => {
    e.preventDefault();
    
    if (!draggedIdea) return;
    
    try {
      await socialAPI.updateIdea(draggedIdea.id, { status: targetStatus as any });
      await loadIdeasData();
    } catch (error) {
      console.error('Failed to update idea status:', error);
    } finally {
      setDraggedIdea(null);
    }
  };

  // Idea management handlers
  const handleCreateIdea = async () => {
    try {
      await socialAPI.createIdea(newIdea);
      await loadIdeasData();
      setShowCreateModal(false);
      resetNewIdeaForm();
    } catch (error) {
      console.error('Failed to create idea:', error);
      alert('Failed to create idea. Please try again.');
    }
  };

  const handleGenerateAIIdeas = async () => {
    setIsGeneratingAI(true);
    try {
      const generatedIdeas = await socialAPI.generateAIIdeas(aiRequest);
      
      // Create ideas from AI suggestions
      for (const aiIdea of generatedIdeas) {
        await socialAPI.createIdea({
          title: aiIdea.title,
          description: aiIdea.description,
          content_draft: aiIdea.content,
          tags: aiIdea.tags || [],
          category: aiIdea.category || 'general',
          target_platforms: [aiRequest.platform],
          priority: 2,
          ai_generated: true
        });
      }
      
      await loadIdeasData();
      setShowAIModal(false);
    } catch (error) {
      console.error('Failed to generate AI ideas:', error);
      alert('Failed to generate AI ideas. Please try again.');
    } finally {
      setIsGeneratingAI(false);
    }
  };

  const handleConvertToPost = async (ideaId: string) => {
    try {
      const post = await socialAPI.convertIdeaToPost(ideaId);
      navigate(`../create-post?from_idea=${ideaId}`);
    } catch (error) {
      console.error('Failed to convert idea to post:', error);
      alert('Failed to convert idea to post. Please try again.');
    }
  };

  const handleDeleteIdea = async (ideaId: string) => {
    if (!window.confirm('Are you sure you want to delete this idea?')) return;
    
    try {
      await socialAPI.deleteIdea(ideaId);
      await loadIdeasData();
    } catch (error) {
      console.error('Failed to delete idea:', error);
      alert('Failed to delete idea. Please try again.');
    }
  };

  // Helper functions
  const resetNewIdeaForm = () => {
    setNewIdea({
      title: '',
      description: '',
      content_draft: '',
      tags: [],
      category: '',
      target_platforms: [],
      priority: 1
    });
  };

  const addTag = (tag: string) => {
    if (tag && !newIdea.tags.includes(tag)) {
      setNewIdea(prev => ({
        ...prev,
        tags: [...prev.tags, tag]
      }));
    }
  };

  const removeTag = (tagToRemove: string) => {
    setNewIdea(prev => ({
      ...prev,
      tags: prev.tags.filter(tag => tag !== tagToRemove)
    }));
  };

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 1: return 'text-gray-500';
      case 2: return 'text-brand-800';
      case 3: return 'text-yellow-500';
      case 4: return 'text-orange-500';
      case 5: return 'text-red-500';
      default: return 'text-gray-500';
    }
  };

  const getPriorityLabel = (priority: number) => {
    switch (priority) {
      case 1: return 'Low';
      case 2: return 'Normal';
      case 3: return 'Medium';
      case 4: return 'High';
      case 5: return 'Critical';
      default: return 'Normal';
    }
  };

  // Filter ideas based on search and category
  const filteredIdeas = ideas.filter(idea => {
    const matchesSearch = idea.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         idea.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || idea.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const categories = Array.from(new Set(ideas.map(idea => idea.category).filter(Boolean)));

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-5 gap-6">
            {Array(5).fill(0).map((_, i) => (
              <div key={i} className="space-y-4">
                <div className="h-6 bg-gray-200 rounded"></div>
                {Array(3).fill(0).map((_, j) => (
                  <div key={j} className="h-32 bg-gray-200 rounded"></div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Ideas Board</h1>
            <p className="text-gray-600 mt-1">Organize and develop your social media content ideas</p>
          </div>
          
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setShowAIModal(true)}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center space-x-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>AI Generate</span>
            </button>
            
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2 bg-brand-800 text-white rounded-lg hover:bg-brand-900 transition-colors"
            >
              + New Idea
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center space-x-4">
          <div className="flex-1">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search ideas..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
            />
          </div>
          
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
          >
            <option value="all">All Categories</option>
            {categories.map(category => (
              <option key={category} value={category}>
                {category.charAt(0).toUpperCase() + category.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Kanban Board */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6">
        {columns.map((column) => (
          <div
            key={column.id}
            className={`${column.color} rounded-lg p-4 min-h-96`}
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, column.status)}
          >
            {/* Column Header */}
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">{column.title}</h3>
              <span className="bg-white px-2 py-1 rounded-full text-xs font-medium text-gray-600">
                {column.ideas.length}
              </span>
            </div>

            {/* Ideas */}
            <div className="space-y-3">
              {column.ideas
                .filter(idea => {
                  const matchesSearch = idea.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                                       idea.description.toLowerCase().includes(searchTerm.toLowerCase());
                  const matchesCategory = selectedCategory === 'all' || idea.category === selectedCategory;
                  return matchesSearch && matchesCategory;
                })
                .map((idea) => (
                <div
                  key={idea.id}
                  draggable
                  onDragStart={() => handleDragStart(idea)}
                  onClick={() => setSelectedIdea(idea)}
                  className="bg-white p-4 rounded-lg shadow-sm border cursor-move hover:shadow-md transition-shadow"
                >
                  {/* Idea Header */}
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="font-medium text-gray-900 text-sm leading-tight flex-1">
                      {idea.title}
                    </h4>
                    {idea.ai_generated && (
                      <span className="ml-2 flex-shrink-0 text-purple-500" title="AI Generated">
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                      </span>
                    )}
                  </div>
                  
                  {/* Description */}
                  <p className="text-xs text-gray-600 mb-3 line-clamp-2">
                    {idea.description}
                  </p>
                  
                  {/* Tags */}
                  {idea.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {idea.tags.slice(0, 3).map((tag, idx) => (
                        <span key={idx} className="px-2 py-1 bg-brand-100 text-brand-800 text-xs rounded-full">
                          #{tag}
                        </span>
                      ))}
                      {idea.tags.length > 3 && (
                        <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                          +{idea.tags.length - 3}
                        </span>
                      )}
                    </div>
                  )}
                  
                  {/* Platforms */}
                  <div className="flex items-center justify-between">
                    <div className="flex space-x-1">
                      {idea.target_platforms.slice(0, 3).map((platformName, idx) => {
                        const platform = platforms.find(p => p.name === platformName);
                        return (
                          <div
                            key={idx}
                            className="w-4 h-4 rounded-full"
                            style={{ backgroundColor: platform?.color_hex || '#6B7280' }}
                            title={platform?.display_name}
                          />
                        );
                      })}
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <span className={`text-xs font-medium ${getPriorityColor(idea.priority)}`}>
                        {getPriorityLabel(idea.priority)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Create Idea Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Create New Idea</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input
                  type="text"
                  value={newIdea.title}
                  onChange={(e) => setNewIdea(prev => ({ ...prev, title: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
                  placeholder="Enter idea title..."
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={newIdea.description}
                  onChange={(e) => setNewIdea(prev => ({ ...prev, description: e.target.value }))}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
                  placeholder="Describe your idea..."
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Content Draft</label>
                <textarea
                  value={newIdea.content_draft}
                  onChange={(e) => setNewIdea(prev => ({ ...prev, content_draft: e.target.value }))}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
                  placeholder="Draft your content..."
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <input
                  type="text"
                  value={newIdea.category}
                  onChange={(e) => setNewIdea(prev => ({ ...prev, category: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
                  placeholder="e.g., promotional, educational, behind-the-scenes"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                <select
                  value={newIdea.priority}
                  onChange={(e) => setNewIdea(prev => ({ ...prev, priority: Number(e.target.value) }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
                >
                  <option value={1}>Low</option>
                  <option value={2}>Normal</option>
                  <option value={3}>Medium</option>
                  <option value={4}>High</option>
                  <option value={5}>Critical</option>
                </select>
              </div>
              
              <div className="flex space-x-3 pt-4">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateIdea}
                  disabled={!newIdea.title.trim()}
                  className="flex-1 px-4 py-2 bg-brand-800 text-white rounded-lg hover:bg-brand-900 disabled:opacity-50 transition-colors"
                >
                  Create Idea
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* AI Generation Modal */}
      {showAIModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Generate AI Ideas</h3>
              <button
                onClick={() => setShowAIModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Business Type</label>
                <input
                  type="text"
                  value={aiRequest.business_type}
                  onChange={(e) => setAiRequest(prev => ({ ...prev, business_type: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
                  placeholder="e.g., construction, home improvement"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Platform</label>
                <select
                  value={aiRequest.platform}
                  onChange={(e) => setAiRequest(prev => ({ ...prev, platform: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
                >
                  {platforms.map(platform => (
                    <option key={platform.id} value={platform.name}>
                      {platform.display_name}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Number of Ideas</label>
                <select
                  value={aiRequest.count}
                  onChange={(e) => setAiRequest(prev => ({ ...prev, count: Number(e.target.value) }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-800"
                >
                  <option value={3}>3 ideas</option>
                  <option value={5}>5 ideas</option>
                  <option value={10}>10 ideas</option>
                </select>
              </div>
              
              <div className="flex space-x-3 pt-4">
                <button
                  onClick={() => setShowAIModal(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleGenerateAIIdeas}
                  disabled={isGeneratingAI}
                  className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors flex items-center justify-center"
                >
                  {isGeneratingAI ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Generating...
                    </>
                  ) : (
                    'Generate Ideas'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Idea Detail Modal */}
      {selectedIdea && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">{selectedIdea.title}</h3>
              <button
                onClick={() => setSelectedIdea(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <p className="text-gray-600 text-sm">{selectedIdea.description}</p>
              </div>
              
              {selectedIdea.content_draft && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Content Draft</label>
                  <div className="p-3 border border-gray-200 rounded-lg bg-gray-50 text-sm">
                    {selectedIdea.content_draft}
                  </div>
                </div>
              )}
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                  <p className="text-gray-600 text-sm">{selectedIdea.category || 'No category'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                  <p className={`text-sm font-medium ${getPriorityColor(selectedIdea.priority)}`}>
                    {getPriorityLabel(selectedIdea.priority)}
                  </p>
                </div>
              </div>
              
              {selectedIdea.tags.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tags</label>
                  <div className="flex flex-wrap gap-1">
                    {selectedIdea.tags.map((tag, idx) => (
                      <span key={idx} className="px-2 py-1 bg-brand-100 text-brand-800 text-xs rounded-full">
                        #{tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              <div className="flex space-x-3 pt-4">
                <button
                  onClick={() => handleDeleteIdea(selectedIdea.id)}
                  className="px-4 py-2 border border-red-300 text-red-700 rounded-lg hover:bg-red-50 transition-colors"
                >
                  Delete
                </button>
                <button
                  onClick={() => handleConvertToPost(selectedIdea.id)}
                  className="flex-1 px-4 py-2 bg-brand-800 text-white rounded-lg hover:bg-brand-900 transition-colors"
                >
                  Convert to Post
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IdeasBoard;