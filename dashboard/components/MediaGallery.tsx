'use client'
import { useState, useEffect } from 'react'
import { getTerrainGallery, getVideoGallery, generateGallery } from '../lib/api'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function MediaGallery() {
  const [images, setImages] = useState<any[]>([])
  const [videos, setVideos] = useState<any[]>([])
  const [generating, setGenerating] = useState(false)
  const [scene, setScene] = useState('Mars terrain exploration, Jezero Crater')
  const [tab, setTab] = useState<'images' | 'videos'>('images')

  const refresh = async () => {
    const [img, vid] = await Promise.all([getTerrainGallery(12), getVideoGallery(8)])
    setImages(img.images)
    setVideos(vid.videos)
  }

  useEffect(() => { refresh() }, [])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      await generateGallery(scene, 4, 2)
      await refresh()
    } catch (e) {
      console.error(e)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-orange-400 font-bold text-sm tracking-widest uppercase">Mission Media Gallery</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setTab('images')}
            className={`text-xs px-3 py-1 rounded ${tab === 'images' ? 'bg-orange-600 text-white' : 'bg-gray-700 text-gray-300'}`}
          >
            Images ({images.length})
          </button>
          <button
            onClick={() => setTab('videos')}
            className={`text-xs px-3 py-1 rounded ${tab === 'videos' ? 'bg-orange-600 text-white' : 'bg-gray-700 text-gray-300'}`}
          >
            Videos ({videos.length})
          </button>
        </div>
      </div>

      {/* Generate controls */}
      <div className="flex gap-2 mb-4">
        <input
          value={scene}
          onChange={e => setScene(e.target.value)}
          className="flex-1 bg-gray-800 border border-gray-600 text-gray-200 text-xs rounded px-3 py-2"
          placeholder="Scene context for generation..."
        />
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="bg-orange-600 hover:bg-orange-500 disabled:bg-gray-600 text-white text-xs px-4 py-2 rounded font-bold"
        >
          {generating ? 'Generating...' : '⚡ Generate'}
        </button>
        <button onClick={refresh} className="bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs px-3 py-2 rounded">
          ↻
        </button>
      </div>

      {/* Image grid */}
      {tab === 'images' && (
        <div className="grid grid-cols-3 gap-2">
          {images.length === 0 && (
            <p className="col-span-3 text-gray-500 text-xs text-center py-8">
              No terrain images yet. Click Generate to create some.
            </p>
          )}
          {images.map((img, i) => (
            <div key={i} className="relative group rounded overflow-hidden bg-gray-800 aspect-video">
              <img
                src={`${API}/terrain/gallery/${img.file}`}
                alt={`Mars terrain ${i + 1}`}
                className="w-full h-full object-cover"
              />
              <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-gray-300 text-xs p-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {img.size_kb}KB · {new Date(img.ts * 1000).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Video grid */}
      {tab === 'videos' && (
        <div className="grid grid-cols-2 gap-3">
          {videos.length === 0 && (
            <p className="col-span-2 text-gray-500 text-xs text-center py-8">
              No videos yet. Click Generate to create some.
            </p>
          )}
          {videos.map((vid, i) => (
            <div key={i} className="rounded overflow-hidden bg-gray-800">
              <video
                src={`${API}/video/gallery/${vid.file}`}
                controls
                className="w-full aspect-video"
                preload="metadata"
              />
              <div className="text-gray-400 text-xs p-2">
                {vid.size_kb}KB · {new Date(vid.ts * 1000).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
