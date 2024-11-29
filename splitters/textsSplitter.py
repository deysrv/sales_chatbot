from typing import List,Dict
import re
import json

class RecursiveTextChunker:
    """Handles hierarchical chunking of content using multiple splitters and chunk size."""

    def __init__(self, splitters=["\n\n","\n","."," "], chunk_size: int = 2000, overlap: int = 500):
        """
        Initialize the chunker with hierarchical splitters, chunk size, and optional overlap.

        Args:
            splitters (List[str]): A list of hierarchical splitters, starting from the largest.
            chunk_size (int): Maximum size of a chunk (characters). Chunks may be smaller if split naturally.
            overlap (int): Number of overlapping characters between consecutive chunks (optional).
        """
        if overlap >= chunk_size:
            raise ValueError("Overlap must be smaller than chunk size.")
        self.splitters = splitters
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, data: List[Dict[str, str]]) -> List[str]:
        """
        Chunk content hierarchically based on splitters and chunk size.

        Args:
            data (List[Dict[str, Any]]): A list of dictionaries with content and metadata.

        Returns:
            List[str]: A list of chunks with updated metadata.
        """
        chunks = []
        overlap_content=""
        overlap_metadata={}
        for pages in data:
            content = pages["content"]+" "+overlap_content
            metadata = pages["metadata"]
            # Merge current page metadata with the previous page's metadata for the overlap
            if overlap_metadata != metadata and len(overlap_metadata) != 0:
                # Merge the metadata dictionaries
                merged_metadata={}
                for key in metadata.keys():

                    merged_metadata[key] = str({metadata.get(key, set())} | {overlap_metadata.get(key, set())})
            else:
                merged_metadata = metadata
            chunks.extend(self._split_hierarchically(content, merged_metadata))
            overlap_content=content[-self.overlap:] if self.overlap > 0 else ""
            overlap_metadata = metadata
        return chunks

    def _split_hierarchically(self, content: str, metadata: str) -> List[str]:
        """Split content hierarchically based on the list of splitters."""
        segments = [content]
        for splitter in self.splitters:
            segments = self._split_by_delimiter(segments, splitter)

        # Available size for content per chunk
        metadata_size = len(str(metadata))
        max_content_size = self.chunk_size - metadata_size

        #ignore chunks which can't be made smaller than the given chunk size by the splitters
        segments=[chunk[:max_content_size] for chunk in segments]

        # Combine segments into chunks respecting chunk_size and overlap
        return self._combine_segments_into_chunks(segments, metadata)

    def _split_by_delimiter(self, segments: List[str], delimiter: str) -> List[str]:
        """Split each segment by the given delimiter."""
        split_segments = []
        for segment in segments:
            if len(segment) > self.chunk_size:  # Only split if the segment exceeds the chunk size
                split_segments.extend(segment.split(delimiter))
            else:
                split_segments.append(segment)
        return [seg.strip() for seg in split_segments if seg.strip()]

    def _combine_segments_into_chunks(self, segments: List[str], metadata: str) -> List[str]:
        """
        Creating sliding window and chunking the content while ensuring that the combined size of chunk
        and metadata does not exceed the max size=chunk_size-metadata_size.
        """
        chunks = []
        current_chunk = []
        current_size = 0

        metadata_size = len(str(metadata))

        if metadata_size >= self.chunk_size:
            raise ValueError("Metadata size exceeds or equals the chunk size limit.")

        # Available size for content per chunk
        max_content_size = self.chunk_size - metadata_size

        for segment in segments:
            segment_length = len(segment)
            if current_size + segment_length <= max_content_size:
                # Add segment to the current chunk
                current_chunk.append(segment)
                current_size += segment_length
            else:
                # Save the current chunk, ensuring the combined size is within the limit
                chunk_content = " ".join(current_chunk).strip()
                if len(chunk_content) + metadata_size > self.chunk_size:
                    # Split the oversized chunk further
                    split_chunks = self._split_by_length(chunk_content, max_content_size)
                    for split_chunk in split_chunks:
                        chunks.append({"content": split_chunk,"metadata": metadata})
                else:
                    chunks.append({"content": chunk_content,"metadata": metadata})

                # Handle overlap
                overlap_content = " ".join(current_chunk)[-self.overlap:] if self.overlap > 0 else ""
                
                # Start a new chunk
                current_chunk = [overlap_content, segment]
                current_size = len(overlap_content) + segment_length

        # Handle the final chunk
        if current_chunk:
            final_content = " ".join(current_chunk).strip()
            if len(final_content) + metadata_size > self.chunk_size:
                # Split the final oversized chunk further
                split_chunks = self._split_by_length(final_content, max_content_size)
                for split_chunk in split_chunks:
                    chunks.append({"content": split_chunk,"metadata": metadata})
            else:
                # Add the final chunk
                chunks.append({"content": final_content,"metadata": metadata})

        return chunks


    def _split_by_length(self, content: str, max_content_size:int) -> List[str]:
        """Helper function to split a string into chunks of max length chunk_size."""
        return [content[i:i + max_content_size] for i in range(0, len(content), max_content_size)]
    
    def _extract_metadata(self, string: str):
        """Helper function for extracting metadata"""
        match = re.search(r"\{(.+?)\}", string)
        return set(match.group(1).split(",")) if match else set()