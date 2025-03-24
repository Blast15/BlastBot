import discord
from discord.ext import commands
from discord import app_commands
import os
import re
import sys
import subprocess
import traceback
import urllib.error
import tempfile
from pytube import YouTube

# Try to import yt-dlp as a fallback
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    
from utils.embed_helpers import create_error_embed, create_success_embed, create_processing_embed

class Youtube(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Check if ffmpeg is available
        self._check_ffmpeg()
        # Check if yt-dlp is available
        if YTDLP_AVAILABLE:
            self.bot.logger.info("yt-dlp is available as a fallback")
        else:
            self.bot.logger.warning("yt-dlp is not available. Install with: pip install yt-dlp")

    def _check_ffmpeg(self):
        """Check if ffmpeg is available on the system"""
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.bot.logger.info("ffmpeg is available on the system")
            self.ffmpeg_available = True
        except Exception:
            self.bot.logger.warning("ffmpeg is not available on the system. MP3 conversion may not work properly.")
            self.ffmpeg_available = False

    @commands.hybrid_command(name="youtube2mp3", description="Chuyển đổi video YouTube thành file mp3")
    @app_commands.describe(url="Liên kết video YouTube")
    async def youtube2mp3(self, ctx, url: str):
        """
        Downloads a YouTube video and converts it to MP3 format.
        
        Args:
            url: The YouTube video URL
        """
        try:
            # Check if interaction is deferred
            if isinstance(ctx.interaction, discord.Interaction):
                await ctx.interaction.response.defer(ephemeral=False)
            
            # Validate YouTube URL
            if not self._is_valid_youtube_url(url):
                await ctx.send(embed=create_error_embed("URL không hợp lệ. Vui lòng cung cấp URL YouTube hợp lệ."))
                return
            
            # Send processing message
            processing_msg = await ctx.send(embed=create_processing_embed("⏳ Đang xử lý video YouTube..."))
            
            # Create temporary directory for files
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Try with pytube first
                    success = await self._download_with_pytube(ctx, url, temp_dir, processing_msg)
                    
                    # If pytube fails and yt-dlp is available, try with yt-dlp
                    if not success and YTDLP_AVAILABLE:
                        self.bot.logger.info(f"Falling back to yt-dlp for URL: {url}")
                        await processing_msg.edit(embed=create_processing_embed("⏳ Đang thử lại bằng phương pháp khác..."))
                        success = await self._download_with_ytdlp(ctx, url, temp_dir, processing_msg)
                        
                    # If all methods failed
                    if not success:
                        await processing_msg.delete()
                        await ctx.send(embed=create_error_embed("Không thể tải xuống video. Vui lòng kiểm tra URL hoặc thử lại sau."))
                        
                except Exception as e:
                    await processing_msg.delete()
                    error_message = str(e)
                    traceback_str = traceback.format_exc()
                    self.bot.logger.error(f"Lỗi khi xử lý YouTube: {error_message}\n{traceback_str}")
                    await ctx.send(embed=create_error_embed(f"Lỗi khi xử lý video: {error_message}"))
        
        except Exception as e:
            error_message = str(e)
            traceback_str = traceback.format_exc()
            self.bot.logger.error(f"Lỗi trong lệnh youtube2mp3: {error_message}\n{traceback_str}")
            await ctx.send(embed=create_error_embed(f"Lỗi: {error_message}"))
    
    async def _download_with_pytube(self, ctx, url, temp_dir, processing_msg):
        """Download and process YouTube video using pytube"""
        try:
            yt = YouTube(url)
            video_title = yt.title
            
            # Get audio stream with highest quality
            audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            
            if not audio_stream:
                self.bot.logger.warning(f"No audio stream found for: {url}")
                return False
            
            # Create safe filename
            safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            if not safe_title:
                safe_title = "youtube_audio"
                
            temp_file = os.path.join(temp_dir, f"temp_{safe_title}.mp4")
            output_file = os.path.join(temp_dir, f"{safe_title}.mp3")
            
            # Download audio
            self.bot.logger.info(f"Downloading audio from YouTube: {url}")
            audio_stream.download(filename=temp_file)
            self.bot.logger.info(f"Download completed: {temp_file}")
            
            # Convert to MP3
            success = await self._convert_to_mp3(temp_file, output_file)
            if not success:
                return False
                
            # Send the mp3 file
            await self._send_mp3_file(ctx, output_file, video_title, processing_msg)
            return True
            
        except urllib.error.HTTPError as e:
            self.bot.logger.error(f"HTTP Error with pytube: {str(e)}")
            return False
        except Exception as e:
            self.bot.logger.error(f"Error with pytube: {str(e)}")
            return False
    
    async def _download_with_ytdlp(self, ctx, url, temp_dir, processing_msg):
        """Download and process YouTube video using yt-dlp"""
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            
            # If ffmpeg is not available, disable post-processing
            if not self.ffmpeg_available:
                ydl_opts.pop('postprocessors', None)
            
            # Download video with yt-dlp
            self.bot.logger.info(f"Downloading with yt-dlp: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_title = info.get('title', 'youtube_audio')
                
                if self.ffmpeg_available:
                    # yt-dlp with ffmpeg will create .mp3 files
                    output_file = os.path.join(temp_dir, f"{video_title}.mp3")
                else:
                    # Without ffmpeg, we'll have the original format
                    ext = info.get('ext', 'mp4')
                    original_file = os.path.join(temp_dir, f"{video_title}.{ext}")
                    output_file = os.path.join(temp_dir, f"{video_title}.mp3")
                    # Try to convert or just rename
                    if not await self._convert_to_mp3(original_file, output_file):
                        # If conversion fails, just rename
                        os.rename(original_file, output_file)
            
            # Check if file exists
            if not os.path.exists(output_file):
                for file in os.listdir(temp_dir):
                    if file.endswith('.mp3'):
                        output_file = os.path.join(temp_dir, file)
                        break
            
            if not os.path.exists(output_file):
                self.bot.logger.error(f"Output file not found after yt-dlp download")
                return False
                
            # Send the mp3 file
            await self._send_mp3_file(ctx, output_file, video_title, processing_msg)
            return True
            
        except Exception as e:
            self.bot.logger.error(f"Error with yt-dlp: {str(e)}")
            return False
            
    async def _convert_to_mp3(self, input_file, output_file):
        """Convert audio file to MP3 format"""
        if not os.path.exists(input_file):
            self.bot.logger.error(f"Input file does not exist: {input_file}")
            return False
            
        if self.ffmpeg_available:
            self.bot.logger.info(f"Converting {input_file} to {output_file} using ffmpeg")
            process = subprocess.run(
                ['ffmpeg', '-i', input_file, '-vn', '-ab', '128k', '-ar', '44100', '-y', output_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            if process.returncode != 0:
                self.bot.logger.error(f"ffmpeg conversion failed: {process.stderr.decode('utf-8')}")
                return False
        else:
            # Without ffmpeg, just rename file
            self.bot.logger.info(f"ffmpeg not available, renaming {input_file} to {output_file}")
            os.rename(input_file, output_file)
        
        return os.path.exists(output_file)
    
    async def _send_mp3_file(self, ctx, output_file, video_title, processing_msg):
        """Send MP3 file to the Discord channel"""
        # Check file size (Discord limit for non-Nitro is 8MB)
        file_size = os.path.getsize(output_file)
        if file_size > 8 * 1024 * 1024:
            await processing_msg.edit(embed=create_processing_embed("⏳ File quá lớn, đang nén..."))
            # Compress the audio file by reducing bitrate
            filename, ext = os.path.splitext(output_file)
            compressed_file = f"{filename}_compressed{ext}"
            
            if self.ffmpeg_available:
                process = subprocess.run(
                    ['ffmpeg', '-i', output_file, '-b:a', '96k', '-y', compressed_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                if process.returncode == 0 and os.path.exists(compressed_file):
                    output_file = compressed_file
                    
            # Check file size again
            file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
            if file_size_mb > 8:
                await processing_msg.delete()
                await ctx.send(embed=create_error_embed(f"File quá lớn để gửi ({file_size_mb:.2f}MB). Discord giới hạn tệp 8MB."))
                return
                
        # Send the mp3 file
        await processing_msg.delete()
        self.bot.logger.info(f"Sending file: {output_file} ({os.path.getsize(output_file) / (1024 * 1024):.2f} MB)")
        
        await ctx.send(
            embed=create_success_embed(f"✅ Đã chuyển đổi thành công: {video_title}"),
            file=discord.File(output_file)
        )
        
    def _is_valid_youtube_url(self, url):
        """Check if the provided URL is a valid YouTube URL."""
        youtube_regex = (
            r'(https?://)?(www\.)?'
            r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        )
        youtube_match = re.match(youtube_regex, url)
        return youtube_match is not None

async def setup(bot):
    await bot.add_cog(Youtube(bot))
