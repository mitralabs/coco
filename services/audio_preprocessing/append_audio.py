import os
from pydub import AudioSegment
import shutil
import re

def append_session_audio(base_dir="_data", output_dir="appended_audio", delete_source=False):
    """
    Append audio files from session directories and save as single files.
    
    Args:
        base_dir (str): Path containing session folders (_data/session_X/)
        output_dir (str): Path for saving appended files
        delete_source (bool): Whether to delete original files after processing
    
    Returns:
        list: List of processed session directories
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all session directories
    session_dirs = [d for d in os.listdir(base_dir) 
                   if os.path.isdir(os.path.join(base_dir, d)) 
                   and d.startswith('session_')]
    
    processed_sessions = []
    
    for session_dir in sorted(session_dirs):
        print(f"\nProcessing {session_dir}")
        session_path = os.path.join(base_dir, session_dir)
        
        # Get all wav files in session directory
        audio_files = sorted([f for f in os.listdir(session_path) 
                            if f.endswith('.wav')])
        
        # Sort according to increment number
        audio_files.sort(key=lambda f: int(re.search(r'audio_\d+_(\d+)\.wav', f).group(1)))

        print(audio_files)
        if not audio_files:
            print(f"No audio files found in {session_dir}")
            continue
            
        try:
            # Combine audio files
            combined = AudioSegment.from_wav(os.path.join(session_path, audio_files[0]))
            for audio_file in audio_files[1:]:
                audio_path = os.path.join(session_path, audio_file)
                audio = AudioSegment.from_wav(audio_path)
                combined += audio
            
            # Save combined audio
            output_path = os.path.join(output_dir, f"{session_dir}.wav")
            combined.export(output_path, format="wav")
            processed_sessions.append(session_dir)
            print(f"Created: {output_path}")
            
            # Delete source files if requested
            if delete_source:
                shutil.rmtree(session_path)
                print(f"Deleted source directory: {session_path}")
                
        except Exception as e:
            print(f"Error processing {session_dir}: {str(e)}")
            continue
    
    print("\nProcessing complete!")
    return processed_sessions

if __name__ == "__main__":
    processed = append_session_audio(delete_source=False)
    print(f"Processed sessions: {processed}")