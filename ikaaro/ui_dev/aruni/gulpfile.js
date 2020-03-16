/* Requirements */
var gulp = require("gulp"),
    colors = require('ansi-colors'),
    log = require('fancy-log'),
    sass = require('gulp-sass');
    concat = require('gulp-concat'),
    taskListing = require('gulp-task-listing');


function errorPrint(msg) {
  log(colors.red.bold('ERROR'), msg);
}


/************
 * Tasks
 ***********/

gulp.task('help', taskListing);
gulp.task('default', taskListing);
gulp.task('build-aruni', function() {
  var pCSS = function () {
    return new Promise(function (resolve, reject) {
      var cssStream = gulp.src('css/scss/style.scss')
               .pipe(sass())
               .pipe(concat('style.css'))
               .pipe(gulp.dest('./dist/'))
               .pipe(gulp.dest('../../ui/aruni/dist/'))
               .on('end', function () {
                    log('CSS OK');
                    resolve();
               });
    });
  };

  // Copy font awesome fonts
  gulp.src('node_modules/font-awesome/fonts/*.*')
     .pipe(gulp.dest('./dist/fonts/'))
     .pipe(gulp.dest('../../ui/aruni/dist/fonts/'));

  // Run
  return pCSS().catch(function (error) {
      errorPrint(error);
  });
});


gulp.task("build", gulp.series("build-aruni"));
