# Candidate visits and ground-cover labels (plan-minimum.md, Sun step 1).
# Run from the project root:  Rscript R/extract_labels.R
#
# 1. Select the candidate visits. Rules are in docs/decisions.md:
#    on/after 2017-03-28, plot aligned to the grid, panorama photos within
#    7 days of the visit, and at least 3 sequences with 7+ frames.
# 2. Calculate green / dry / bare with ground_fractional = TRUE (F9).
#    "Dry" is `brown`. Unknown / NA hits are removed and the three
#    fractions are scaled again so that they add to 100.
#
# Frame listings are cached in data/frames/ (one JSON per visit), so a
# second run does not ask TERN again and the photo step can reuse them.

suppressMessages({
  library(ausplotsR)
  library(jsonlite)
})

S2_START   <- as.Date("2017-03-28")  # Earth Engine S2_SR_HARMONIZED start
MAX_GAP    <- 7                      # days between survey and photo date
MIN_FRAMES <- 7                      # first frame is dropped, 6 remain
MIN_SEQ    <- 3                      # usable sequences a visit needs
API        <- "https://ecoimages.tern.org.au/api/v1.0/search?site_id=ausplots"
FRAME_DIR  <- "data/frames"

step <- function(label, n) cat(sprintf("%-46s %5d\n", label, n))

# --- 1a. AusPlots visits: date and grid filters -----------------------------
si <- get_ausplots(site_info = TRUE)$site.info
si$visit_date <- as.Date(substr(si$visit_start_date, 1, 10))
step("AusPlots visits", nrow(si))
si <- si[!is.na(si$visit_date) & si$visit_date >= S2_START, ]
step("  on/after 2017-03-28", nrow(si))
si <- si[si$plot_is_aligned_to_grid %in% TRUE, ]
step("  and plot aligned to the grid", nrow(si))

# --- 1b. Match each visit to the closest panorama date at the same site -----
pano <- data.frame()
for (p in 1:50) {
  h <- fromJSON(sprintf("%s&image_type=panorama&page_size=1000&page_num=%d", API, p))$hits$hits
  if (length(h) == 0) break
  pano <- rbind(pano, data.frame(site_location_name = h$`_source`$plot$label,
                                 photo_id = h$`_source`$site_visit_id))
}
pano <- unique(pano)
pano$photo_date <- as.Date(pano$photo_id, "%Y%m%d")

m <- merge(si[, c("site_unique", "site_location_name", "visit_date", "latitude", "longitude")],
           pano, by = "site_location_name")
m$date_gap <- abs(as.numeric(m$photo_date - m$visit_date))
m <- do.call(rbind, lapply(split(m, m$site_unique), function(x) x[which.min(x$date_gap), ]))
visits <- m[m$date_gap <= MAX_GAP, ]
step("  and panorama photos within 7 days", nrow(visits))

# --- 1c. Count usable photo sequences for each visit ------------------------
dir.create(FRAME_DIR, recursive = TRUE, showWarnings = FALSE)

frame_listing <- function(site, photo_id) {
  path <- file.path(FRAME_DIR, sprintf("%s_%s.json", site, photo_id))
  if (!file.exists(path)) {
    u <- sprintf("%s&image_type=photopoint&plot=ausplots.%s&site_visit_id=%s&page_size=200",
                 API, tolower(site), photo_id)
    for (try in 1:3) {
      txt <- tryCatch(readLines(u, warn = FALSE), error = function(e) NULL)
      if (!is.null(txt)) break
      Sys.sleep(5 * try)
    }
    if (is.null(txt)) stop("TERN did not answer after 3 tries: ", u)
    writeLines(txt, path)
  }
  j <- fromJSON(path)
  total <- j$hits$total
  if (is.list(total)) total <- total$value
  n <- if (length(j$hits$hits) == 0) 0 else nrow(j$hits$hits)
  if (n < total) stop("frame listing truncated for ", path)
  if (n == 0) return(integer(0))
  as.integer(table(j$hits$hits$`_source`$position$value))
}

visits$n_seq_usable <- mapply(function(s, d) sum(frame_listing(s, d) >= MIN_FRAMES),
                              visits$site_location_name, visits$photo_id)
visits <- visits[visits$n_seq_usable >= MIN_SEQ, ]
step("  and 3+ sequences with 7+ frames (candidates)", nrow(visits))

# --- 2. Ground-layer labels for the candidate visits ------------------------
pi <- get_ausplots(my.Plot_IDs = unique(visits$site_location_name),
                   site_info = FALSE, veg.PI = TRUE)$veg.PI
fc <- fractional_cover(pi, ground_fractional = TRUE)

# Remove unknown / NA hits, then scale the three fractions to 100.
# `na_pct` is the percent of hits that were unknown. ausplotsR 2.0.5 names
# this column "other" (older docs call it "NA"). It is saved in visits.csv so
# that visits with many removed hits can be found.
stopifnot("other" %in% names(fc))   # fail loudly if the package renames it again
for (col in c("green", "brown", "bare", "other")) {
  fc[[col]][is.na(fc[[col]])] <- 0
}
fc$total <- fc$green + fc$brown + fc$bare
labels <- data.frame(site_unique = fc$site_unique,
                     na_pct = fc$other,
                     raw_sum = fc$total + fc$other,
                     green = 100 * fc$green / fc$total,
                     dry   = 100 * fc$brown / fc$total,
                     bare  = 100 * fc$bare  / fc$total)

labels <- merge(visits[, c("site_unique", "site_location_name", "visit_date",
                           "latitude", "longitude")],
                labels, by = "site_unique")
names(labels)[names(labels) == "site_location_name"] <- "site"
step("Candidate visits with ground-cover labels", nrow(labels))

missing <- setdiff(visits$site_unique, labels$site_unique)
if (length(missing) > 0) cat("No labels for:", paste(missing, collapse = ", "), "\n")
stopifnot(all(abs(labels$green + labels$dry + labels$bare - 100) < 1e-6))
cat(sprintf("Before scaling, green+dry+bare+other = %.2f to %.2f\n",
            min(labels$raw_sum), max(labels$raw_sum)))
cat(sprintf("Unknown ('other') hits removed: mean %.2f%%, max %.2f%%; %d visits above 0%%, %d above 10%%\n",
            mean(labels$na_pct), max(labels$na_pct),
            sum(labels$na_pct > 0), sum(labels$na_pct > 10)))
stopifnot(!anyDuplicated(labels[, c("site", "visit_date")]))
cat("OK: every label row adds to 100.\n")

# --- 3. Save ----------------------------------------------------------------
labels <- labels[order(labels$site, labels$visit_date), ]
write.csv(labels[, c("site", "visit_date", "latitude", "longitude", "green", "dry", "bare")],
          "data/labels.csv", row.names = FALSE)

visits <- merge(visits[visits$site_unique %in% labels$site_unique, ],
                labels[, c("site_unique", "na_pct")], by = "site_unique")
names(visits)[names(visits) == "site_location_name"] <- "site"
visits <- visits[order(visits$site, visits$visit_date), ]
write.csv(visits[, c("site", "site_unique", "visit_date", "photo_id", "photo_date",
                     "date_gap", "n_seq_usable", "na_pct")],
          "data/visits.csv", row.names = FALSE)
cat("Saved data/labels.csv and data/visits.csv:", nrow(labels), "visits\n")
