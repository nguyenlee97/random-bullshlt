const mongoose = require('mongoose');

// Full audience segment from Audience Library.xlsx
const audienceLibrarySchema = new mongoose.Schema(
  {
    segmentId:   { type: String, required: true, unique: true, index: true }, // INT001, BEH001, etc.
    type:        { type: String, required: true, enum: ['Interest', 'Behavior'], index: true },
    category:    { type: String, default: '' },
    subcategory: { type: String, default: null },
    name:        { type: String, required: true },
    context:     { type: String, default: null },
    fullLabel:   { type: String, default: '' },
    sizeMin:     { type: Number, default: null },
    sizeMax:     { type: Number, default: null },
    sizeRaw:     { type: String, default: null },
  },
  {
    collection: 'audience_library',
    timestamps: false,
  }
);

// Index for category filtering
audienceLibrarySchema.index({ type: 1, category: 1 });

module.exports = mongoose.model('AudienceLibrary', audienceLibrarySchema);
