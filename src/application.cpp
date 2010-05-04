/*
 * Toonloop
 *
 * Copyright 2010 Alexandre Quessy
 * <alexandre@quessy.net>
 * http://www.toonloop.com
 *
 * Toonloop is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Toonloop is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the gnu general public license
 * along with Toonloop.  If not, see <http://www.gnu.org/licenses/>.
 */
#include <GL/glew.h>
#include "application.h"
#include "gui.h"
#include "pipeline.h"
#include "pipeline.h"
#include <iostream>
#include <string>
#include <gtk/gtk.h>
#include <boost/program_options.hpp>
#include <boost/filesystem.hpp>
#include <cstdlib> // for getenv
#include "config.h"
#include <gtk/gtk.h>
#include <gst/gst.h>
#include "clip.h"
#include "videoconfig.h"

namespace po = boost::program_options;
namespace fs = boost::filesystem;

Application* Application::instance_ = 0;

Application::Application() 
{
    for (int i = 0; i < 10; i++)
    {
        clips_[i] = new Clip(i);
    }
    selected_clip_ = 0;
}

Clip* Application::get_current_clip()
{
    return clips_[selected_clip_];
}

/**
 * Parses the command line and runs the application.
 */
void Application::run(int argc, char *argv[])
{
    std::string video_source = "/dev/video0";
    std::string toonloop_home = "~/Documents/toonloop";
    if (! fs::exists(video_source))
        video_source = "videotestsrc";
    po::options_description desc("Toonloop options");
    std::cout << "adding options" << std::endl;
    desc.add_options()
        ("help,h", "Show this help message and exit")
        ("toonloop-home,H", po::value<std::string>()->default_value(toonloop_home), "Path to the saved files")
        ("version", "Show program's version number and exit")
        ("verbose,v", po::bool_switch(), "Enables a verbose output")
        //("intervalometer-on,i", po::bool_switch(), "Enables the intervalometer to create time lapse animations")
        //("intervalometer-interval,I", po::value<double>()->default_value(5.0), "Sets the intervalometer rate in seconds")
        ("project-name,p", po::value<std::string>()->default_value("default"), "Sets the name of the project for image saving")
        ("display,D", po::value<std::string>()->default_value(std::getenv("DISPLAY")), "Sets the X11 display name")
        //("rendering-fps", po::value<int>()->default_value(30), "Rendering frame rate") // FIXME: can we get a FPS different for the rendering?
        //("capture-fps,r", po::value<int>()->default_value(30), "Rendering frame rate")
        ("playhead-fps", po::value<int>()->default_value(12), "Playback rate of Clip Sequence, to be controlled by user")
        //("image-width,w", po::value<int>()->default_value(640), "Width of the images grabbed from the camera. Default is 640")
        //("image-height,y", po::value<int>()->default_value(480), "Height of the images grabbed from the camera. Default is 480")
        ("fullscreen,f", po::bool_switch(), "Runs in fullscreen mode.")
        ("video-source,d", po::value<std::string>()->default_value(video_source), "Sets the video source or device. Use \"test\" for color bars.");
    po::variables_map options;
    po::store(po::parse_command_line(argc, argv, desc), options);
    po::notify(options);
    if (options.count("help"))
    {
        std::cout << desc << std::endl;
        return;
    }
    if (options.count("version"))
    {
        std::cout << PACKAGE << " " << PACKAGE_VERSION << std::endl;
        return; 
    }
    if (options.count("video-source"))
    {
        video_source = options["video-source"].as<std::string>();
        if (video_source != "test")
        {
            if (! fs::exists(video_source))
            {
                std::cout << "No such device file: " << video_source << std::endl;
                exit(1); // exit with error
            }
        }
        std::cout << "video-source is set to " << video_source << std::endl;
    }
    if (options.count("toonloop-home"))
    {
        toonloop_home = options["toonloop-home"].as<std::string>();
        if (toonloop_home == "~/Documents/toonloop")
            toonloop_home = std::string(std::getenv("HOME")) + "/Documents/toonloop";
        std::cout << "toonloop-home is set to " << toonloop_home << std::endl;
        if (! fs::exists(toonloop_home))
        {
            try 
            {
                fs::create_directories(toonloop_home); // TODO: check if it returns true
            } catch(const std::exception& e) {
                // TODO: be more specific to fs::basic_filesystem_error<Path> 
                std::cerr << "An error occured while creating the directory: " << e.what() << std::endl;
            }
        } else {
            if (! fs::is_directory(toonloop_home))
            {
                std::cout << "Error: " << toonloop_home << " is not a directory." << std::endl;
                exit(1);
            }
        }
    }
    // FIXME: From there, the options are set in videoconfig.cpp
    // TODO: We should do this in only one place. 
#if 0
    if (options["intervalometer-on"].as<bool>())
        std::cout << "Intervalometer is on. (but not yet implemented)" << std::endl;
    if (options.count("intervalometer-interval"))
        std::cout << "The rate of the intervalometer is set to " << options["intervalometer-interval"].as<double>() << std::endl; 
#endif
    if (options.count("project-name"))
    {
        // TODO
        std::cout << "The project name is set to " << options["project-name"].as<std::string>() << std::endl;
    }
    
    if (options.count("playhead-fps"))
    { 
        std::cout << "The initial frame rate for clip playhead is set to " << options["playhead-fps"].as<int>() << std::endl;
        for (int i = 0; i < clips_.size(); i++)
        {
            clips_[i]->set_playhead_fps(options["playhead-fps"].as<int>());
        }
    }

    if (options["fullscreen"].as<bool>())
    {
        std::cout << "Fullscreen mode is on: " << std::endl;
        std::cout << "Fullscreen mode is on: " << options["fullscreen"].as<bool>() << std::endl;
    }
    
    // Stores the options in the VideoConfig class.
    VideoConfig config(options);
    config.set_toonloop_home(toonloop_home);

    // Init GTK:
    gtk_init(&argc, &argv);
    // Init GST:
    gst_init(&argc, &argv);
    // start GUI
    std::cout << "Starting GUI." << std::endl;
    gui_ = std::tr1::shared_ptr<Gui>(new Gui());
    // start Pipeline
    std::cout << "Starting pipeline." << std::endl;
    pipeline_ = std::tr1::shared_ptr<Pipeline>(new Pipeline(config));
    // set drawing area TODO: simplify this
    get_pipeline().set_drawing_area(get_gui().get_drawing_area());
    std::cout << "Running toonloop" << std::endl;
    gtk_main();
}

Pipeline& Application::get_pipeline() 
{
    return *pipeline_;
}
Gui& Application::get_gui() 
{
    return *gui_;
}

Application& Application::get_instance()
{
    if (!instance_)
        instance_ = new Application();
    return *instance_;
}

// delete the instance
// FIXME: not sure how safe this is
void Application::reset()
{
    std::cout << "Resetting the application" << std::endl;
    delete instance_;
    instance_ = 0;
}

void Application::quit()
{
    std::cout << "Quitting the application." << std::endl;
    get_pipeline().stop();
    gtk_main_quit();
}
